<?php
// This script provides CPU and Memory usage as a JSON object.

// Set header to output JSON
header('Content-Type: application/json');

/**
 * Calculates the current system-wide CPU usage percentage.
 * It does this by reading /proc/stat twice with a 1-second delay.
 * @return float|string The CPU usage percentage, or 'N/A' on failure.
 */
function get_cpu_usage() {
    // Read initial CPU stats
    $stat1_str = @file_get_contents('/proc/stat');
    if ($stat1_str === false) { return 'N/A'; }
    
    // Extract the first line (aggregate CPU stats)
    $stat1_lines = explode("\n", $stat1_str);
    $stat1_data = preg_split('/[[:space:]]+/', trim($stat1_lines[0]));

    $prev_idle = (int)($stat1_data[4] ?? 0) + (int)($stat1_data[5] ?? 0); // idle + iowait
    $prev_total = array_sum(array_slice($stat1_data, 1));

    // Wait for a second to get a delta
    sleep(1);

    // Read CPU stats again
    $stat2_str = @file_get_contents('/proc/stat');
    if ($stat2_str === false) { return 'N/A'; }

    $stat2_lines = explode("\n", $stat2_str);
    $stat2_data = preg_split('/[[:space:]]+/', trim($stat2_lines[0]));

    $idle = (int)($stat2_data[4] ?? 0) + (int)($stat2_data[5] ?? 0);
    $total = array_sum(array_slice($stat2_data, 1));

    // Calculate the differences
    $diff_idle = $idle - $prev_idle;
    $diff_total = $total - $prev_total;
    
    if ($diff_total == 0) { return 0; }
    
    // Calculate the percentage of time spent idle, then subtract from 100
    $cpu_usage = 100.0 - ($diff_idle / $diff_total) * 100.0;

    return round($cpu_usage, 2);
}

/**
 * Calculates the current system memory usage.
 * It reads /proc/meminfo and prefers 'MemAvailable' for accuracy.
 * @return array|string An array with memory details, or 'N/A' on failure.
 */
function get_memory_usage() {
    $meminfo_str = @file_get_contents('/proc/meminfo');
    if ($meminfo_str === false) { return 'N/A'; }
    
    preg_match('/MemTotal:\s+(\d+)/', $meminfo_str, $matches_total);
    preg_match('/MemAvailable:\s+(\d+)/', $meminfo_str, $matches_avail);

    if (!isset($matches_total[1])) { return 'N/A'; }
    $mem_total = (int)$matches_total[1];

    if (isset($matches_avail[1])) {
        // Modern kernels: Use MemAvailable for a more accurate reading
        $mem_available = (int)$matches_avail[1];
    } else {
        // Fallback for older kernels
        preg_match('/MemFree:\s+(\d+)/', $meminfo_str, $matches_free);
        preg_match('/Buffers:\s+(\d+)/', $meminfo_str, $matches_buffers);
        preg_match('/Cached:\s+(\d+)/', $meminfo_str, $matches_cached);
        $mem_available = ((int)$matches_free[1] ?? 0) + ((int)$matches_buffers[1] ?? 0) + ((int)$matches_cached[1] ?? 0);
    }
    
    if ($mem_total == 0) {
        return ['used_gb' => 0, 'total_gb' => 0, 'percent' => 0];
    }
    
    $mem_used = $mem_total - $mem_available;
    
    return [
        'used_gb' => round($mem_used / 1024 / 1024, 2),
        'total_gb' => round($mem_total / 1024 / 1024, 2),
        'percent' => round(($mem_used / $mem_total) * 100, 1)
    ];
}

// Assemble the final stats object
$stats = [
    'cpu_percent' => get_cpu_usage(),
    'mem_info'    => get_memory_usage(),
];

// Output as JSON
echo json_encode($stats);
?>
