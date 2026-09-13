<?php
declare(strict_types=1);
require __DIR__ . '/_init.php';

$user = api_user();
$pdo = db();

// This endpoint stores the device-neutral Just InCard account snapshot.  It is
// deliberately independent from the older browser/dashboard tables so an
// existing 1.0.0 account remains valid and no collection data is rewritten by
// merely upgrading the web files.
$pdo->exec(
    'CREATE TABLE IF NOT EXISTS account_sync_payloads (
        user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
        revision BIGINT UNSIGNED NOT NULL DEFAULT 0,
        schema_name VARCHAR(80) NOT NULL DEFAULT "justincard-account-sync-v1",
        source_device VARCHAR(120) NOT NULL DEFAULT "",
        payload MEDIUMTEXT NOT NULL,
        updated_at DATETIME NOT NULL,
        CONSTRAINT fk_account_sync_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
     ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci'
);

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $stmt = $pdo->prepare(
        'SELECT revision, schema_name, source_device, payload, updated_at
         FROM account_sync_payloads WHERE user_id = ? LIMIT 1'
    );
    $stmt->execute([(int)$user['id']]);
    $row = $stmt->fetch();
    if (!$row) {
        json_response([
            'ok' => true,
            'revision' => 0,
            'schema' => 'justincard-account-sync-v1',
            'source_device' => '',
            'updated_at' => null,
            'payload' => [
                'schema' => 'justincard-account-sync-v1',
                'collection' => [],
                'decks' => [],
            ],
        ]);
    }
    $payload = json_decode((string)$row['payload'], true);
    if (!is_array($payload)) {
        $payload = ['schema' => 'justincard-account-sync-v1', 'collection' => [], 'decks' => []];
    }
    json_response([
        'ok' => true,
        'revision' => (int)$row['revision'],
        'schema' => (string)$row['schema_name'],
        'source_device' => (string)$row['source_device'],
        'updated_at' => (string)$row['updated_at'],
        'payload' => $payload,
    ]);
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST' && $_SERVER['REQUEST_METHOD'] !== 'PUT') {
    json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

$data = json_input();
$payload = $data['payload'] ?? null;
$sourceDevice = trim((string)($data['source_device'] ?? ''));
$ifRevision = array_key_exists('if_revision', $data) ? (int)$data['if_revision'] : null;

if (!is_array($payload)) {
    json_response(['ok' => false, 'error' => 'invalid_payload', 'message' => 'payload muss ein JSON-Objekt sein.'], 422);
}
$schema = trim((string)($payload['schema'] ?? $data['schema'] ?? 'justincard-account-sync-v1'));
if ($schema !== 'justincard-account-sync-v1') {
    json_response(['ok' => false, 'error' => 'unsupported_schema'], 422);
}
if (!isset($payload['collection']) || !is_array($payload['collection']) || !isset($payload['decks']) || !is_array($payload['decks'])) {
    json_response(['ok' => false, 'error' => 'invalid_payload', 'message' => 'collection und decks müssen Arrays sein.'], 422);
}

$encoded = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
if ($encoded === false) {
    json_response(['ok' => false, 'error' => 'invalid_json'], 422);
}
// Prevent accidental huge uploads. No card-image bytes belong in this store.
if (strlen($encoded) > 12 * 1024 * 1024) {
    json_response(['ok' => false, 'error' => 'payload_too_large'], 413);
}

$pdo->beginTransaction();
try {
    $lock = $pdo->prepare('SELECT revision FROM account_sync_payloads WHERE user_id = ? FOR UPDATE');
    $lock->execute([(int)$user['id']]);
    $row = $lock->fetch();
    $currentRevision = $row ? (int)$row['revision'] : 0;
    if ($ifRevision !== null && $ifRevision !== $currentRevision) {
        $pdo->rollBack();
        json_response([
            'ok' => false,
            'error' => 'revision_conflict',
            'revision' => $currentRevision,
            'message' => 'Der Serverstand wurde zwischenzeitlich geändert. Bitte erneut synchronisieren.',
        ], 409);
    }

    $nextRevision = $currentRevision + 1;
    $stmt = $pdo->prepare(
        'INSERT INTO account_sync_payloads
         (user_id, revision, schema_name, source_device, payload, updated_at)
         VALUES (?, ?, ?, ?, ?, NOW())
         ON DUPLICATE KEY UPDATE
           revision = VALUES(revision), schema_name = VALUES(schema_name),
           source_device = VALUES(source_device), payload = VALUES(payload), updated_at = NOW()'
    );
    $stmt->execute([
        (int)$user['id'],
        $nextRevision,
        $schema,
        substr($sourceDevice, 0, 120),
        $encoded,
    ]);
    $pdo->commit();
} catch (Throwable $e) {
    if ($pdo->inTransaction()) $pdo->rollBack();
    json_response(['ok' => false, 'error' => 'database_error'], 500);
}

json_response([
    'ok' => true,
    'revision' => $nextRevision,
    'schema' => $schema,
    'updated_at' => gmdate('Y-m-d H:i:s'),
]);
