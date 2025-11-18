<?php
// This part handles the POST request from the JavaScript fetch call
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Disable execution time limit for this script, as loading the model can be slow.
    set_time_limit(0);

    // Get the JSON payload sent from the frontend
    $json_data = file_get_contents('php://input');
    
    // The Python Flask server URL.
    // IMPORTANT: If your Python server is on a different machine, replace 127.0.0.1 with its IP address.
    $ai_server_url = 'http://127.0.0.1:5000/ask';

    // Set headers for streaming text and disable compression.
    header('Content-Type: text/plain; charset=utf-8');
    header('X-Content-Type-Options: nosniff');
    header('Content-Encoding: none;');

    // Disable PHP's output buffering.
    while (ob_get_level() > 0) {
        ob_end_clean();
    }

    // --- Primary Method: Try connecting to the running server ---
    $ch = curl_init($ai_server_url);

    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $json_data);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5); // Add a 5-second connection timeout
    
    // This function is called for each chunk of data received from the server.
    curl_setopt($ch, CURLOPT_WRITEFUNCTION, function($curl, $data) {
        // Echo the chunk immediately to the browser.
        echo $data;
        // Flush the output buffer.
        flush();
        // Return the number of bytes written.
        return strlen($data);
    });

    // Execute the request
    curl_exec($ch);
    $curl_error_num = curl_errno($ch);
    $curl_error_msg = curl_error($ch);
    curl_close($ch);

    // --- Fallback Method: If server connection failed, run script directly ---
    if ($curl_error_num === CURLE_COULDNT_CONNECT) {
        echo "[Warning: AI server not running. Using slower direct execution mode...]\n\n";
        flush();
        
        $data = json_decode($json_data, true);

        if (empty($data['question'])) {
            http_response_code(400);
            echo "Error: No question provided in fallback mode.";
            exit;
        }
        
        // Build the command for direct execution
        $python_script_path = './ai.py';
        $command = 'python3 ' . escapeshellarg($python_script_path) . ' -q ' . escapeshellarg($data['question']);

        // Add system prompt if provided
        if (!empty($data['system_prompt'])) {
            $command .= ' -s ' . escapeshellarg($data['system_prompt']);
        }

        // Add other generation parameters from the JSON payload
        $params = [
            'temperature'    => '-t', 'top_k' => '--top_k', 'top_p' => '--top_p',
            'repeat_penalty' => '--repeat_penalty', 'max_tokens' => '--max_tokens',
            'mirostat_mode'  => '--mirostat_mode', 'mirostat_tau' => '--mirostat_tau',
            'mirostat_eta'   => '--mirostat_eta',
        ];

        foreach ($params as $key => $cli_arg) {
            if (isset($data[$key]) && $data[$key] !== '') {
                $command .= ' ' . $cli_arg . ' ' . escapeshellarg($data[$key]);
            }
        }

        // Use proc_open for real-time streaming
        $descriptorspec = [0 => ["pipe", "r"], 1 => ["pipe", "w"], 2 => ["pipe", "w"]];
        $process = proc_open($command, $descriptorspec, $pipes);

        if (is_resource($process)) {
            fclose($pipes[0]);

            // Stream standard output
            while ($line = fread($pipes[1], 1024)) {
                echo $line;
                flush();
            }

            // After the process finishes, we will no longer display the stderr logs.
            /*
            $stderr_output = stream_get_contents($pipes[2]);
            if (!empty($stderr_output)) {
                echo "\n\n--- SCRIPT ERRORS ---\n";
                echo $stderr_output;
                flush();
            }
            */

            fclose($pipes[1]);
            fclose($pipes[2]);
            proc_close($process);
        } else {
            http_response_code(500);
            echo "Error: Could not execute the AI model script in fallback mode.";
        }
    } else if ($curl_error_num !== 0) {
        // Handle other, unexpected cURL errors
        http_response_code(503);
        echo "An unexpected error occurred while connecting to the AI service.\n\n";
        echo "cURL Error (" . $curl_error_num . "): " . htmlspecialchars($curl_error_msg) . "\n\n";
        echo "This might be a firewall issue. Please ensure port 5000 is accessible from your web server.\n";
        echo "You can test this with: curl http://127.0.0.1:5000";
    }

    exit;
}

// --- Helper function to check if the Python server is running ---
function is_ai_server_running($host, $port, $timeout = 1) {
    // Use fsockopen to attempt a connection without a long wait.
    $fp = @fsockopen($host, $port, $errno, $errstr, $timeout);
    if ($fp) {
        fclose($fp);
        return true;
    }
    return false;
}

// --- Main Page Logic (GET request) ---
$is_server_running = is_ai_server_running('127.0.0.1', 5000);
$default_system_prompt = "You are a helpful assistant. Keep your answers concise.";
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat with AI (PHP)</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: auto; padding: 20px; background-color: #f4f4f4; color: #333; }
        h1, h2 { color: #333; }
        #qa-form { display: flex; flex-direction: column; margin-bottom: 20px; }
        #question-container { display: flex; }
        #question { flex-grow: 1; padding: 10px; border: 1px solid #ccc; border-radius: 4px; }
        button { padding: 10px 15px; border: none; background-color: #007bff; color: white; border-radius: 4px; cursor: pointer; margin-left: 10px; }
        button:hover { background-color: #0056b3; }
        button:disabled { background-color: #cccccc; }
        #response-container { background-color: white; padding: 15px; border-radius: 4px; border: 1px solid #ddd; min-height: 50px; }
        #response { white-space: pre-wrap; }
        details { margin-top: 15px; border: 1px solid #ccc; border-radius: 4px; padding: 10px; }
        summary { cursor: pointer; font-weight: bold; }
        .param-grid { display: grid; grid-template-columns: 150px 1fr; gap: 10px; align-items: center; margin-top: 10px;}
        .param-grid label { font-weight: bold; }
        .param-grid input, .param-grid textarea, .param-grid select { width: 100%; box-sizing: border-box; padding: 5px; border-radius: 4px; border: 1px solid #ccc;}
        .param-grid textarea { resize: vertical; min-height: 60px; }
        .slider-container { display: flex; align-items: center; gap: 10px; }
        .slider-container input { flex-grow: 1; }
        .slider-container span { min-width: 35px; text-align: right; }
        .prompt-notice { font-style: italic; color: #555; margin-bottom: 5px; }
        #stop-button { background-color: #dc3545; }
        #stop-button:hover { background-color: #c82333; }
        .status-box { padding: 10px 15px; margin-bottom: 20px; border-radius: 4px; border: 1px solid; }
        .status-ok { background-color: #d4edda; border-color: #c3e6cb; color: #155724; }
        .status-warn { background-color: #fff3cd; border-color: #ffeeba; color: #856404; }
        .status-box code { background-color: rgba(0,0,0,0.05); padding: 2px 4px; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="status-box <?php echo $is_server_running ? 'status-ok' : 'status-warn'; ?>">
        <?php if ($is_server_running): ?>
            <strong>Status:</strong> Connected to the fast AI backend server.
        <?php else: ?>
            <strong>Status:</strong> AI backend server not running. Using slow fallback mode.
            <br>
            <small>For fast responses, start the server: <code>python3 /home/asher/public_html/ai.py</code></small>
        <?php endif; ?>
    </div>

    <h1>Ask your local AI model a question?</h1>
    <form id="qa-form" action="ai.php" method="post">
        <div id="question-container">
            <input type="text" id="question" name="question" placeholder="Type your question here..." required autocomplete="off">
            <button type="submit" id="ask-button">Ask</button>
            <button type="button" id="stop-button" style="display: none;">Stop</button>
        </div>
        <details>
            <summary>Advanced Options</summary>
            <div class="param-grid">
                <label for="system_prompt">System Prompt:</label>
                <textarea id="system_prompt" placeholder="<?php echo htmlspecialchars($default_system_prompt); ?>"></textarea>
                
                <label for="temperature">Temperature:</label>
                <div class="slider-container">
                    <input type="range" id="temperature" min="0" max="2" step="0.05" value="2.0">
                    <span id="temperature-value">2.0</span>
                </div>

                <label for="max_tokens">Max Tokens:</label>
                <input type="number" id="max_tokens" value="1024" min="1">
                
                <label for="top_k">Top K:</label>
                <input type="number" id="top_k" value="0" min="0">

                <label for="top_p">Top P:</label>
                 <div class="slider-container">
                    <input type="range" id="top_p" min="0" max="1" step="0.05" value="1.0">
                    <span id="top_p-value">1.0</span>
                </div>

                <label for="repeat_penalty">Repeat Penalty:</label>
                <div class="slider-container">
                    <input type="range" id="repeat_penalty" min="1" max="2" step="0.05" value="1.1">
                    <span id="repeat_penalty-value">1.1</span>
                </div>

                <label for="mirostat_mode">Mirostat Mode:</label>
                <select id="mirostat_mode">
                    <option value="0">Disabled</option>
                    <option value="1">Mirostat v1</option>
                    <option value="2" selected>Mirostat v2</option>
                </select>

                <label for="mirostat_tau">Mirostat Tau:</label>
                <div class="slider-container">
                    <input type="range" id="mirostat_tau" min="0" max="10" step="0.1" value="5.0">
                    <span id="mirostat_tau-value">5.0</span>
                </div>

                <label for="mirostat_eta">Mirostat Eta:</label>
                <div class="slider-container">
                    <input type="range" id="mirostat_eta" min="0" max="1" step="0.01" value="0.1">
                    <span id="mirostat_eta-value">0.1</span>
                </div>
            </div>
        </details>
    </form>
    <h2>Answer:</h2>
    <div id="response-container">
        <p id="response">The answer will appear here.</p>
    </div>

    <script>
        let abortController = null;

        function setupSlider(sliderId, displayId) {
            const slider = document.getElementById(sliderId);
            const display = document.getElementById(displayId);
            slider.addEventListener('input', () => display.textContent = slider.value);
        }

        setupSlider('temperature', 'temperature-value');
        setupSlider('top_p', 'top_p-value');
        setupSlider('repeat_penalty', 'repeat_penalty-value');
        setupSlider('mirostat_tau', 'mirostat_tau-value');
        setupSlider('mirostat_eta', 'mirostat_eta-value');

        document.getElementById('stop-button').addEventListener('click', () => {
            if (abortController) {
                abortController.abort();
            }
        });

        document.getElementById('qa-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const questionInput = document.getElementById('question');
            const responseP = document.getElementById('response');
            const askButton = document.getElementById('ask-button');
            const stopButton = document.getElementById('stop-button');

            abortController = new AbortController();

            const payload = {
                question: document.getElementById('question').value,
                system_prompt: document.getElementById('system_prompt').value,
                temperature: document.getElementById('temperature').value,
                max_tokens: document.getElementById('max_tokens').value,
                top_k: document.getElementById('top_k').value,
                top_p: document.getElementById('top_p').value,
                repeat_penalty: document.getElementById('repeat_penalty').value,
                mirostat_mode: document.getElementById('mirostat_mode').value,
                mirostat_tau: document.getElementById('mirostat_tau').value,
                mirostat_eta: document.getElementById('mirostat_eta').value,
            };

            responseP.textContent = 'Thinking...';
            askButton.disabled = true;
            stopButton.style.display = 'inline-block';

            try {
                const response = await fetch('ai.php', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    signal: abortController.signal
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let isFirstChunk = true;

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    if (isFirstChunk) {
                        responseP.textContent = '';
                        isFirstChunk = false;
                    }
                    responseP.textContent += decoder.decode(value, { stream: true });
                }

            } catch (error) {
                if (error.name === 'AbortError') {
                    responseP.textContent = 'Response stopped by user.';
                    console.log('Fetch aborted by user.');
                } else {
                    console.error('Fetch error:', error);
                    // If we started receiving data and then the connection broke, it's likely a server timeout.
                    if (isFirstChunk === false) {
                        responseP.textContent += '\n\n[Error: The connection was lost mid-stream. This is likely due to a server timeout because the AI model is very slow to load. For better performance, please run the AI server in the background.]';
                    } else {
                        responseP.textContent = 'An error occurred while fetching the response: ' + error.message + '\n\n[Debug Tip: If the page hangs on "Thinking...", the AI server might be stuck. Check its logs for errors using the command: `bash /home/asher/public_html/ai_server_control.sh logs`]';
                    }
                }
            } finally {
                askButton.disabled = false;
                stopButton.style.display = 'none';
                questionInput.value = '';
                abortController = null;
            }
        });
    </script>
</body>
</html>