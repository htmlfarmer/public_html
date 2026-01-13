<?php
session_start();
require __DIR__ . '/src/OpenAIClient.php';
require __DIR__ . '/src/GoogleAIClient.php';

// On POST, handle data then redirect to prevent form resubmission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
  // Always update the provider in the session from the POST data
  $_SESSION['provider'] = $_POST['provider'] ?? 'google';

  if (isset($_POST['save_key'])) {
    $keyName = $_SESSION['provider'] === 'google' ? 'GOOGLE_API_KEY' : 'OPENAI_API_KEY';
    $_SESSION[$keyName] = trim($_POST['api_key'] ?? '');
  }
  if (isset($_POST['clear_key'])) {
    $keyName = $_SESSION['provider'] === 'google' ? 'GOOGLE_API_KEY' : 'OPENAI_API_KEY';
    unset($_SESSION[$keyName]);
  }

  // Handle 'send' action for both providers
  if (isset($_POST['send'])) {
    $prompt = trim($_POST['prompt'] ?? '');
    $_SESSION['prompt'] = $prompt; // Save prompt for repopulating textarea

    if (empty($prompt)) {
      $_SESSION['error'] = 'Please enter a prompt.';
    } else {
        try {
            if ($_SESSION['provider'] === 'google') {
                $apiKey = $_SESSION['GOOGLE_API_KEY'] ?? getenv('GOOGLE_API_KEY');
                if (empty($apiKey)) {
                    $_SESSION['error'] = 'No Google API key configured. Paste it above and click "Save key".';
                } else {
                    $client = new GoogleAIClient($apiKey);
                    $_SESSION['output'] = $client->chat($prompt);
                    unset($_SESSION['error']); // Clear previous errors
                }
            } else { // openai
                $apiKey = $_SESSION['OPENAI_API_KEY'] ?? getenv('OPENAI_API_KEY');
                if (empty($apiKey)) {
                    $_SESSION['error'] = 'No OpenAI API key configured. Paste it above and click "Save key".';
                } else {
                    $client = new OpenAIClient($apiKey);
                    $_SESSION['output'] = $client->chat($prompt);
                    unset($_SESSION['error']); // Clear previous errors
                }
            }
        } catch (Exception $e) {
            $_SESSION['error'] = $e->getMessage();
        }
    }
  }

  // Redirect to self to prevent form resubmission
  header('Location: ' . $_SERVER['PHP_SELF']);
  exit();
}

// On GET, display page and results from session
$provider = $_SESSION['provider'] ?? 'google'; // Default to Google
$output = $_SESSION['output'] ?? '';
$error = $_SESSION['error'] ?? '';
$prompt = $_SESSION['prompt'] ?? ''; // For repopulating textarea

// Clear session variables so they don't show again on next reload
unset($_SESSION['output'], $_SESSION['error'], $_SESSION['prompt']);

// Get current key for the input field
$keyName = $provider === 'google' ? 'GOOGLE_API_KEY' : 'OPENAI_API_KEY';
$currentKey = $_SESSION[$keyName] ?? '';
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>OpenAI PHP Interface</title>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;margin:32px}
    textarea{width:100%;height:140px;margin-bottom:8px}
    pre{white-space:pre-wrap;background:#f6f8fa;padding:12px;border-radius:6px}
    .error{color:#b00020}
    .provider-section{margin-bottom:16px;padding:12px;background:#f0f0f0;border-radius:6px}
  </style>
</head>
<body>
  <h1>OpenAI/Google Gemini PHP Interface (Local)</h1>
  <form method="post">
    <div class="provider-section">
      <label>Provider:</label>
      <label><input type="radio" name="provider" value="openai" <?php echo $provider === 'openai' ? 'checked' : ''; ?> onchange="this.form.submit()"> OpenAI</label>
      <label style="margin-left:16px"><input type="radio" name="provider" value="google" <?php echo $provider === 'google' ? 'checked' : ''; ?> onchange="this.form.submit()"> Google Gemini (Free)</label>
    </div>

    <div>
      <label for="api_key"><?php echo $provider === 'google' ? 'Google API Key' : 'OpenAI API Key'; ?></label><br>
      <input id="api_key" name="api_key" type="password" style="width:60%" value="<?php echo htmlspecialchars($currentKey); ?>">
      <label style="margin-left:8px"><input id="show_key" type="checkbox"> show</label>
    </div>
    <div style="margin-top:8px">
      <button name="save_key" type="submit">Save key</button>
      <button name="clear_key" type="submit">Clear key</button>
    </div>

    <hr>

    <label for="prompt">Prompt</label>
    <textarea id="prompt" name="prompt"><?php echo htmlspecialchars($prompt); ?></textarea>
    <div>
      <button name="send" type="submit" id="send-button">Send</button>
      <button name="clear" type="button" id="clear-button">Clear</button>
    </div>
  </form>

  <?php if ($error): ?>
    <p class="error"><?php echo htmlspecialchars($error); ?></p>
  <?php endif; ?>

  <?php if ($output): ?>
    <h2>Response</h2>
    <pre id="response-output"><?php echo htmlspecialchars($output); ?></pre>
  <?php else: ?>
    <h2>Response</h2>
    <pre id="response-output"></pre>
  <?php endif; ?>

  <script>
    document.getElementById('clear-button').addEventListener('click', function() {
        document.getElementById('prompt').value = '';
        document.getElementById('response-output').textContent = '';
    });

    document.getElementById('show_key').addEventListener('change', function() {
        var apiKeyInput = document.getElementById('api_key');
        if (this.checked) {
            apiKeyInput.type = 'text';
        } else {
            apiKeyInput.type = 'password';
        }
    });
  </script>
</body>
</html>
