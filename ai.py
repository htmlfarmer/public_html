import os
import sys
import argparse
import logging
from llama_cpp import Llama
from flask import Flask, request, render_template_string

# --- Logging Setup ---
# Log to stderr to separate logs from the AI's stdout response.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
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
        """
        Initializes the AI model by loading it into memory.
        """
        self.llm = None
        # CORRECTED: Using the GGUF model path that is known to work.
        self.model_path = "/home/asher/.lmstudio/models/lmstudio-community/gemma-3-1b-it-GGUF/gemma-3-1b-it-Q4_K_M.gguf"
        self.default_system_prompt = "You are a helpful assistant. Keep your answers concise."
        self.max_system_prompt_chars = 8000 # A safe character limit to avoid context overflow

        self.config = {
            # CORRECTED: Restored the proper structure for model parameters.
            "llama_params": {
                "n_ctx": 4096,
                "n_threads": 8,
                "n_gpu_layers": 0,
                "verbose": False
            },
            "generation_params": {
                "temperature": 2.0,
                "top_k": 0,      # Set to 0 to disable Top-K sampling for Mirostat
                "top_p": 1.0,    # Set to 1.0 to disable Top-P sampling for Mirostat
                "repeat_penalty": 1.1,
                "max_tokens": 1024,
                "stop": ["<|eot_id|>"],
                "mirostat_mode": 2,  # Enable Mirostat v2 by default
                "mirostat_tau": 5.0,
                "mirostat_eta": 0.1,
            }
        }
        logging.info("AI Core: Loading model...")
        try:
            with SuppressStderr():
                self.llm = Llama(model_path=self.model_path, **self.config["llama_params"])
            logging.info("AI Core: Model loaded successfully.")
        except Exception as e:
            logging.error(f"!!! FATAL: Error loading model: {e}")
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

        # Combine default params with incoming ones, letting incoming ones overwrite
        final_gen_params = self.config["generation_params"].copy()
        
        # Type conversion and filtering for incoming params
        for key, value in generation_params.items():
            if value is not None and value != '':
                try:
                    if key in ['temperature', 'top_p', 'repeat_penalty', 'mirostat_tau', 'mirostat_eta']:
                        final_gen_params[key] = float(value)
                    elif key in ['top_k', 'max_tokens', 'mirostat_mode']:
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

# This HTML is only used to confirm the server is running when accessed directly.
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI Server Status</title>
</head>
<body>
    <h1>AI Server is Running</h1>
    <p>This is the backend AI server. It is meant to be used with the PHP frontend.</p>
    <p>To use the chat interface, please open <code>ai.php</code> in your browser.</p>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/ask', methods=['POST'])
def ask_route():
    logging.info("Flask /ask: Received a new request.")
    data = request.get_json()
    if not data or not data.get('question'):
        logging.warning("Flask /ask: Request rejected, no question provided.")
        return "Error: No question provided", 400

    user_question = data['question']
    system_prompt_override = data.get('system_prompt', '')
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

# CORRECTED: Restored the proper main execution block for dual CLI/server mode.
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run AI model as a web server or a single-shot command.")
    parser.add_argument('-q', '--question', type=str, help='Question to ask the model in CLI mode.')
    parser.add_argument('-s', '--system_prompt', type=str, default=None, help='System prompt to use, overriding the default.')
    
    # Add other generation params for CLI
    parser.add_argument('-t', '--temperature', type=float, default=None)
    parser.add_argument('--top_k', type=int, default=None)
    parser.add_argument('--top_p', type=float, default=None)
    parser.add_argument('--repeat_penalty', type=float, default=None)
    parser.add_argument('--max_tokens', type=int, default=None)
    parser.add_argument('--mirostat_mode', type=int, default=None)
    parser.add_argument('--mirostat_tau', type=float, default=None)
    parser.add_argument('--mirostat_eta', type=float, default=None)

    args = parser.parse_args()

    # If --question is passed, run in CLI mode
    if args.question:
        system_prompt_override = args.system_prompt
        
        generation_params = {k: v for k, v in vars(args).items() if v is not None and k not in ['question', 'system_prompt']}

        for chunk in ai_model.ask(args.question, system_prompt_override, generation_params):
            print(chunk, end='', flush=True)
        print() # Final newline
    else:
        logging.info("--> Web Server: Starting Flask server...")
        logging.info("--> Web Server: Access the web UI at http://127.0.0.1:5000")
        app.run(host='0.0.0.0', port=5000)