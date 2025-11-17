<?php
// This part handles the POST request from the JavaScript fetch call
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Get the JSON payload sent from the frontend
    $json_data = file_get_contents('php://input');
    $data = json_decode($json_data, true);

    if (empty($data['question'])) {
        http_response_code(400);
        echo "Error: No question provided";
        exit;
    }
    
    // Path to your python executable and script
    $python_script_path = '/home/asher/github/ai/ai.py';
    
    // Start building the command
    $command = 'python3 ' . escapeshellarg($python_script_path);
    $command .= ' -q ' . escapeshellarg($data['question']);

    // Add system prompt if provided
    if (!empty($data['system_prompt'])) {
        $command .= ' -s ' . escapeshellarg($data['system_prompt']);
    }

    // Add other generation parameters from the JSON payload
    $params = [
        'temperature'    => '-t',
        'top_k'          => '--top_k',
        'top_p'          => '--top_p',
        'repeat_penalty' => '--repeat_penalty',
        'max_tokens'     => '--max_tokens',
        'mirostat_mode'  => '--mirostat_mode',
        'mirostat_tau'   => '--mirostat_tau',
        'mirostat_eta'   => '--mirostat_eta',
    ];

    foreach ($params as $key => $cli_arg) {
        if (isset($data[$key]) && $data[$key] !== '') {
            $command .= ' ' . $cli_arg . ' ' . escapeshellarg($data[$key]);
        }
    }

    // Set headers for streaming text and disable compression.
    header('Content-Type: text/plain; charset=utf-8');
    header('X-Content-Type-Options: nosniff');
    header('Content-Encoding: none;');

    // Disable PHP's output buffering.
    while (ob_get_level() > 0) {
        ob_end_clean();
    }

    // Use proc_open for real-time streaming of the command output.
    $descriptorspec = [
       0 => ["pipe", "r"],  // stdin
       1 => ["pipe", "w"],  // stdout
       2 => ["pipe", "w"]   // stderr
    ];

    $process = proc_open($command, $descriptorspec, $pipes);

    if (is_resource($process)) {
        // We don't need to write to the process's stdin
        fclose($pipes[0]);

        // Read the output from the process's stdout stream in a loop
        while ($line = fread($pipes[1], 1024)) {
            // Echo the chunk immediately
            echo $line;
            // Flush the output buffer to the browser
            flush();
        }

        // Clean up
        fclose($pipes[1]);
        fclose($pipes[2]);
        proc_close($process);
    } else {
        http_response_code(500);
        echo "Error: Could not execute the AI model script.";
    }

    exit;
}

// This part handles the GET request and serves the HTML page
$system_prompt_path = "/home/asher/private/system.txt";
$default_system_prompt = "You are a helpful assistant. Keep your answers concise.";
$system_prompt_name = null;

if (file_exists($system_prompt_path)) {
    $prompt_content = file_get_contents($system_prompt_path);
    if ($prompt_content !== false) {
        // The content is only used by the python script, not displayed.
        $system_prompt_name = "O3";
    }
}
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
    </style>
</head>
<body>
    <h1>Ask your local AI model a question?</h1>
    <form id="qa-form" action="ai.php" method="post">
        <div id="question-container">
            <input type="text" id="question" name="question" placeholder="Type your question here..." required autocomplete="off">
            <button type="submit">Ask</button>
        </div>
        <details>
            <summary>Advanced Options</summary>
            <div class="param-grid">
                <label for="system_prompt">System Prompt:</label>
                <div>
                    <?php if ($system_prompt_name): ?>
                    <p class="prompt-notice">Private prompt '<?php echo htmlspecialchars($system_prompt_name); ?>' is loaded. You can add more instructions below.</p>
                    <?php endif; ?>
                    <textarea id="system_prompt" placeholder="Add additional system instructions here..."></textarea>
                </div>
                
                <label for="temperature">Temperature:</label>
                <div class="slider-container">
                    <input type="range" id="temperature" min="0" max="2" step="0.05" value="2.0">
                    <span id="temperature-value">2.0</span>
                </div>

                <label for="max_tokens">Max Tokens:</label>
                <input type="number" id="max_tokens" value="1024" min="1">
                
                <label for="top_k">Top K:</label>
                <input type="number" id="top_k" value="40" min="0">

                <label for="top_p">Top P:</label>
                 <div class="slider-container">
                    <input type="range" id="top_p" min="0" max="1" step="0.05" value="0.95">
                    <span id="top_p-value">0.95</span>
                </div>

                <label for="repeat_penalty">Repeat Penalty:</label>
                <div class="slider-container">
                    <input type="range" id="repeat_penalty" min="1" max="2" step="0.05" value="1.1">
                    <span id="repeat_penalty-value">1.1</span>
                </div>

                <label for="mirostat_mode">Mirostat Mode:</label>
                <select id="mirostat_mode">
                    <option value="0" selected>Disabled</option>
                    <option value="1">Mirostat v1</option>
                    <option value="2">Mirostat v2</option>
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
        // const initialSystemPrompt = <?php echo json_encode($default_system_prompt); ?>;
        // document.getElementById('system_prompt').value = initialSystemPrompt;

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

        document.getElementById('qa-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const questionInput = document.getElementById('question');
            const responseP = document.getElementById('response');
            const submitButton = document.querySelector('#qa-form button');

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
            submitButton.disabled = true;

            try {
                const response = await fetch('ai.php', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
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
                console.error('Fetch error:', error);
                responseP.textContent = 'An error occurred while fetching the response: ' + error.message;
            } finally {
                submitButton.disabled = false;
                questionInput.value = '';
            }
        });
    </script>
</body>
</html>