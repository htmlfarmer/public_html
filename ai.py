import os
import sys
import argparse
import logging
from llama_cpp import Llama
from flask import Flask, request, render_template_string

# --- Logging Setup ---
# Log to stdout, which is redirected to a file by the control script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Suppress llama_cpp's initial output for a cleaner experience
class SuppressStderr:
    def __enter__(self):
        self._original_stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr.close()
        sys.stderr = self._original_stderr

# --- AI Model Class ---
class AIModel:
    def __init__(self):
        self.model_path = '/home/asher/github/ai/models/llama-7b-hf'
        self.default_system_prompt = "You are a helpful assistant. Keep your answers concise."
        self.max_system_prompt_chars = 8000 # A safe character limit to avoid context overflow

        self.config = {
            "model_path": self.model_path,
            "llama_params": {
                "temperature": 0.7,
                "max_tokens": 150,
                "top_k": 50,
                "top_p": 0.95,
                "repeat_penalty": 1.1,
                "mirostat_mode": 0,
                "mirostat_tau": 5.0,
                "mirostat_eta": 0.1,
            }
        }
        logging.info("AI Core: Loading model...")
        try:
            with SuppressStderr():
                self.llm = Llama(model_path=self.config["model_path"], **self.config["llama_params"])
            logging.info("AI Core: Model loaded successfully.")
        except Exception as e:
            logging.error(f"!!! FATAL: Error loading model: {e}")
            # We can also use notify-send here to alert the user of a failure
            os.system(f'notify-send "AI Model Error" "Could not load the language model. Check terminal." -i error')


    def ask(self, user_question, system_prompt_override, generation_params):
        """
        Takes a user's question and params, gets a response from the model, and returns it as a stream generator.
        """
        if not self.llm:
            logging.warning("AIModel.ask: Model not loaded, yielding error.")
            yield "Error: The AI model is not loaded."
            return

        final_system_prompt = system_prompt_override if system_prompt_override else self.default_system_prompt
        logging.info("AIModel.ask: Received new question.")

        # Truncate system_prompt if it's too long to prevent crashes
        if len(final_system_prompt) > self.max_system_prompt_chars:
            final_system_prompt = final_system_prompt[:self.max_system_prompt_chars]
            logging.warning(f"System prompt was too long and was truncated to {self.max_system_prompt_chars} characters.")

        messages = [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": user_question},
        ]

        # Prepare generation parameters, using defaults where not specified
        final_gen_params = {
            "temperature": 0.7,
            "max_tokens": 150,
            "top_k": 50,
            "top_p": 0.95,
            "repeat_penalty": 1.1,
            "mirostat_mode": 0,
            "mirostat_tau": 5.0,
            "mirostat_eta": 0.1,
        }

        # Update with any user-specified parameters, converting types as necessary
        for key, value in generation_params.items():
            if value is not None:
                try:
                    if key in ["temperature", "max_tokens", "top_k", "top_p", "repeat_penalty", "mirostat_tau", "mirostat_eta"]:
                        # Convert to float for these parameters
                        final_gen_params[key] = float(value)
                    elif key == "mirostat_mode":
                        # Convert to int for mirostat_mode
                        final_gen_params[key] = int(value)
                except (ValueError, TypeError):
                    pass # Keep default if conversion fails

        try:
            logging.info("AIModel.ask: Calling create_chat_completion...")
            response_stream = self.llm.create_chat_completion(
                messages=messages,
                stream=True,
                **final_gen_params
            )
            logging.info("AIModel.ask: Stream created. Iterating over chunks...")
            chunk_count = 0
            for chunk in response_stream:
                chunk_count += 1
                content = chunk['choices'][0]['delta'].get('content')
                if content:
                    yield content
            logging.info(f"AIModel.ask: Finished streaming {chunk_count} chunks.")
        except Exception as e:
            logging.error(f"Error during AI generation: {e}")
            yield "Sorry, an error occurred while generating the response."

# --- Web Interface (using Flask) ---

# Check if model loaded successfully before starting the web server
ai_model = AIModel()
if not ai_model.llm:
    logging.critical("!!! FATAL: AI Model not loaded. Web server will not start.")
    exit()

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat with AI (Flask)</title>
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
            <small>Responses may be delayed as the model is reloaded for each request. For fast responses, start the server: <code>bash /home/asher/github/ai/ai_server_control.sh start</code></small>
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
                        responseP.textContent = 'An error occurred while fetching the response: ' + error.message;
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
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, default_system_prompt=ai_model.default_system_prompt)

@app.route('/ask', methods=['POST'])
def ask_route():
    logging.info("Flask /ask: Received a new request.")
    data = request.get_json()
    if not data or not data.get('question'):
        logging.warning("Flask /ask: Request rejected, no question provided.")
        return "Error: No question provided", 400

    user_question = data['question']
    system_prompt_override = data.get('system_prompt')
    generation_params = {
        'temperature': data.get('temperature'),
        'max_tokens': data.get('max_tokens'),
        'top_k': data.get('top_k'),
        'top_p': data.get('top_p'),
        'repeat_penalty': data.get('repeat_penalty'),
        'mirostat_mode': data.get('mirostat_mode'),
        'mirostat_tau': data.get('mirostat_tau'),
        'mirostat_eta': data.get('mirostat_eta'),
    }

    def generate():
        logging.info("Flask /ask: Starting generation stream.")
        for chunk in ai_model.ask(user_question, system_prompt_override, generation_params):
            yield chunk
        logging.info("Flask /ask: Finished generation stream.")

    return app.response_class(generate(), mimetype='text/plain')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="AI Model Server")
    parser.add_argument('-q', '--question', type=str, help="Question to ask the AI model")
    parser.add_argument('-s', '--system_prompt', type=str, help="System prompt for the AI model")
    parser.add_argument('-t', '--temperature', type=float, help="Sampling temperature")
    parser.add_argument('--top_k', type=int, help="Top-k sampling")
    parser.add_argument('--top_p', type=float, help="Top-p (nucleus) sampling")
    parser.add_argument('--repeat_penalty', type=float, help="Repeat penalty")
    parser.add_argument('--mirostat_mode', type=int, help="Mirostat mode")
    parser.add_argument('--mirostat_tau', type=float, help="Mirostat tau")
    parser.add_argument('--mirostat_eta', type=float, help="Mirostat eta")
    args = parser.parse_args()

    # If a question is provided as a command-line argument, bypass the web server and answer directly
    if args.question:
        logging.info("--> Direct Question: " + args.question)
        system_prompt_override = args.system_prompt if args.system_prompt else ai_model.default_system_prompt
        generation_params = {
            'temperature': args.temperature,
            'max_tokens': args.max_tokens,
            'top_k': args.top_k,
            'top_p': args.top_p,
            'repeat_penalty': args.repeat_penalty,
            'mirostat_mode': args.mirostat_mode,
            'mirostat_tau': args.mirostat_tau,
            'mirostat_eta': args.mirostat_eta,
        }
        # Filter out None values
        generation_params = {k: v for k, v in generation_params.items() if v is not None}

        for chunk in ai_model.ask(args.question, system_prompt_override, generation_params):
            print(chunk, end='', flush=True)
        print() # Final newline
    else:
        logging.info("--> Web Server: Starting Flask server...")
        logging.info("--> Web Server: Access the web UI at http://127.0.0.1:5000")
        app.run(host='0.0.0.0', port=5000)