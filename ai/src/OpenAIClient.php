<?php
class OpenAIClient
{
    private $apiKey;
    private $endpoint = 'https://api.openai.com/v1/chat/completions';
    private $model = 'gpt-4o';

    public function __construct(string $apiKey = null)
    {
        if (empty($apiKey)) {
            throw new \Exception('OPENAI_API_KEY not set in environment');
        }
        $this->apiKey = $apiKey;
    }

    public function chat(string $prompt): string
    {
        $payload = [
            'model' => $this->model,
            'messages' => [
                ['role' => 'user', 'content' => $prompt]
            ],
            'max_tokens' => 800,
            'temperature' => 0.7
        ];

        $ch = curl_init($this->endpoint);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Content-Type: application/json',
            'Authorization: Bearer ' . $this->apiKey,
        ]);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));

        $result = curl_exec($ch);
        if (curl_errno($ch)) {
            $err = curl_error($ch);
            curl_close($ch);
            throw new \Exception('cURL error: ' . $err);
        }

        $http = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $json = json_decode($result, true);
        if ($http >= 400) {
            $message = $json['error']['message'] ?? 'Unknown API error';
            throw new \Exception('OpenAI API error (' . $http . '): ' . $message);
        }

        return $json['choices'][0]['message']['content'] ?? json_encode($json);
    }
}
