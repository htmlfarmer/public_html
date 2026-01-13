<?php
class GoogleAIClient
{
    private $apiKey;
    private $endpoint = 'https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent';
    private $model = 'gemini-2.5-flash';

    public function __construct(string $apiKey = null)
    {
        if (empty($apiKey)) {
            throw new \Exception('GOOGLE_API_KEY not set in environment');
        }
        $this->apiKey = $apiKey;
        // Debug: Verify key format
        if (strlen($this->apiKey) < 20) {
            throw new \Exception('API key appears too short. Please verify you copied the full key.');
        }
    }

    public function listModels(): array
    {
        $url = 'https://generativelanguage.googleapis.com/v1/models?key=' . urlencode($this->apiKey);
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Content-Type: application/json',
        ]);

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
            throw new \Exception('Google API error (' . $http . '): ' . $message);
        }

        return $json['models'] ?? [];
    }

    public function chat(string $prompt): string
    {
        $payload = [
            'contents' => [
                [
                    'parts' => [
                        ['text' => $prompt]
                    ]
                ]
            ],
            'generationConfig' => [
                'maxOutputTokens' => 800,
                'temperature' => 0.7
            ]
        ];

        $url = $this->endpoint . '?key=' . urlencode($this->apiKey);
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Content-Type: application/json',
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
            throw new \Exception('Google API error (' . $http . '): ' . $message);
        }

        $text = $json['candidates'][0]['content']['parts'][0]['text'] ?? json_encode($json);
        return $text;
    }

    public function chatStream(string $prompt): void
    {
        header('Content-Type: text/event-stream');
        header('Cache-Control: no-cache');
        header('Connection: keep-alive');

        $payload = [
            'contents' => [
                [
                    'parts' => [
                        ['text' => $prompt]
                    ]
                ]
            ],
            'generationConfig' => [
                'maxOutputTokens' => 800,
                'temperature' => 0.7
            ]
        ];

        $url = str_replace('generateContent', 'streamGenerateContent', $this->endpoint) . '?key=' . urlencode($this->apiKey);
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Content-Type: application/json',
            'Accept: text/event-stream'
        ]);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
        curl_setopt($ch, CURLOPT_WRITEFUNCTION, function ($ch, $data) {
            echo $data;
            ob_flush();
            flush();
            return strlen($data);
        });

        curl_exec($ch);

        if (curl_errno($ch)) {
            $err = curl_error($ch);
            curl_close($ch);
            echo "data: " . json_encode(['error' => 'cURL error: ' . $err]) . "\\n\\n";
            ob_flush();
            flush();
            return;
        }

        curl_close($ch);
    }
}
