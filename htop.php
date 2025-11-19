<?php
// This script provides a standalone, read-only, htop-like system monitor.
set_time_limit(5); // Set a short time limit as this page should render quickly.

// --- Helper Functions ---

/**
 * Gets overall CPU usage. (Simplified version for quick display)
 * @return float CPU usage percentage.
 */
function get_cpu_usage() {
    $stat1 = file('/proc/stat');
    sleep(1);
    $stat2 = file('/proc/stat');
    
    $info1 = explode(" ", preg_replace("! +!", " ", $stat1[0]));
    $info2 = explode(" ", preg_replace("! +!", " ", $stat2[0]));
    
    $prev_idle = (int)($info1[4] ?? 0) + (int)($info1[5] ?? 0);
    $idle = (int)($info2[4] ?? 0) + (int)($info2[5] ?? 0);
    
    $prev_total = array_sum(array_slice($info1, 1));
    $total = array_sum(array_slice($info2, 1));
    
    $diff_idle = $idle - $prev_idle;
    $diff_total = $total - $prev_total;
    
    if ($diff_total == 0) return 0;
    
    return round(100.0 - ($diff_idle / $diff_total) * 100.0, 2);
}

/**
 * Gets memory usage details.
 * @return array Memory information.
 */
function get_memory_usage() {
    $meminfo = @file_get_contents('/proc/meminfo');
    preg_match('/MemTotal:\s+(\d+)/', $meminfo, $total);
    preg_match('/MemAvailable:\s+(\d+)/', $meminfo, $avail);
    
    $mem_total = (int)($total[1] ?? 0);
    $mem_available = (int)($avail[1] ?? 0);
    $mem_used = $mem_total - $mem_available;
    
    return [
        'used_gb' => round($mem_used / 1024 / 1024, 2),
        'total_gb' => round($mem_total / 1024 / 1024, 2),
        'percent' => $mem_total > 0 ? round(($mem_used / $mem_total) * 100, 1) : 0
    ];
}

/**
 * Gets the list of running processes.
 * @return array A list of processes.
 */
function get_process_list() {
    $procs = [];
    $pids = glob('/proc/[0-9]*', GLOB_ONLYDIR);
    
    foreach ($pids as $proc_dir) {
        $pid = basename($proc_dir);
        $status_file = "$proc_dir/status";
        $cmdline_file = "$proc_dir/cmdline";

        if (!is_readable($status_file)) continue;

        $status_content = file_get_contents($status_file);

        preg_match('/^Name:\s+(.*)/m', $status_content, $name);
        preg_match('/^Uid:\s+(\d+)/m', $status_content, $uid);
        preg_match('/^State:\s+(.*)/m', $status_content, $state);
        preg_match('/^VmRSS:\s+(\d+)/m', $status_content, $mem);

        $user_info = posix_getpwuid((int)$uid[1]);
        $command = str_replace("\0", " ", @file_get_contents($cmdline_file));
        if (empty($command)) {
            $command = $name[1];
        }

        $procs[] = [
            'pid' => $pid,
            'user' => $user_info['name'] ?? 'unknown',
            'mem_kb' => (int)($mem[1] ?? 0),
            'state' => $state[1] ?? '?',
            'command' => $command
        ];
    }

    // Sort by memory usage descending
    usort($procs, function($a, $b) {
        return $b['mem_kb'] <=> $a['mem_kb'];
    });
    
    return array_slice($procs, 0, 100); // Limit to top 100 processes
}

/**
 * Gets system load averages.
 * @return string Load averages.
 */
function get_load_average() {
    return file_get_contents('/proc/loadavg');
}

/**
 * Gets system uptime.
 * @return string Formatted uptime.
 */
function get_uptime() {
    $uptime_seconds = (int)explode(' ', file_get_contents('/proc/uptime'))[0];
    $days = floor($uptime_seconds / 86400);
    $hours = floor(($uptime_seconds % 86400) / 3600);
    $minutes = floor(($uptime_seconds % 3600) / 60);
    return sprintf("%d days, %02d:%02d", $days, $hours, $minutes);
}

// --- Data Fetching ---
$cpu_percent = get_cpu_usage();
$mem_info = get_memory_usage();
$load_avg = get_load_average();
$uptime = get_uptime();
$processes = get_process_list();

?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="3">
    <title>htop monitor</title>
    <style>
        body { background-color: #000; color: #fff; font-family: monospace; font-size: 14px; margin: 0; padding: 10px; }
        .header { margin-bottom: 10px; }
        .meter { display: flex; align-items: center; margin-bottom: 2px; }
        .meter-label { min-width: 40px; }
        .meter-bar { flex-grow: 1; height: 16px; background-color: #222; border: 1px solid #555; position: relative; }
        .meter-fill { height: 100%; background-color: #00aaff; }
        .meter-text { position: absolute; left: 5px; top: 0; color: #000; font-weight: bold; }
        .info { color: #00aaff; } .info-label { color: #fff; }
        .proc-table { width: 100%; border-collapse: collapse; }
        .proc-table th { text-align: left; background-color: #222; padding: 2px 5px; }
        .proc-table td { padding: 1px 5px; white-space: pre; }
        .proc-table .pid { color: #fff; }
        .proc-table .user { color: #00ff00; }
        .proc-table .command { color: #ccc; overflow: hidden; text-overflow: ellipsis; max-width: 400px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="meter">
            <div class="meter-label">CPU</div>
            <div class="meter-bar">
                <div class="meter-fill" style="width: <?php echo $cpu_percent; ?>%;"></div>
                <div class="meter-text"><?php echo $cpu_percent; ?>%</div>
            </div>
        </div>
        <div class="meter">
            <div class="meter-label">Mem</div>
            <div class="meter-bar">
                <div class="meter-fill" style="width: <?php echo $mem_info['percent']; ?>%;"></div>
                <div class="meter-text"><?php echo $mem_info['used_gb']; ?>G/<?php echo $mem_info['total_gb']; ?>G</div>
            </div>
        </div>
        <div>
            <span class="info-label">Load average: </span><span class="info"><?php echo htmlspecialchars($load_avg); ?></span>
        </div>
        <div>
            <span class="info-label">Uptime: </span><span class="info"><?php echo htmlspecialchars($uptime); ?></span>
        </div>
    </div>
    <table class="proc-table">
        <thead>
            <tr>
                <th>PID</th>
                <th>User</th>
                <th>MEM (MB)</th>
                <th>State</th>
                <th>Command</th>
            </tr>
        </thead>
        <tbody>
            <?php foreach ($processes as $proc): ?>
            <tr>
                <td class="pid"><?php echo $proc['pid']; ?></td>
                <td class="user"><?php echo htmlspecialchars($proc['user']); ?></td>
                <td><?php echo round($proc['mem_kb'] / 1024, 1); ?></td>
                <td><?php echo htmlspecialchars($proc['state']); ?></td>
                <td class="command"><?php echo htmlspecialchars($proc['command']); ?></td>
            </tr>
            <?php endforeach; ?>
        </tbody>
    </table>
</body>
</html>
