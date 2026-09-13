<?php
declare(strict_types=1);
require_once __DIR__ . '/includes/bootstrap.php';
$user = require_user();
$pdo = db();

$collectionCount = 0;
$totalCards = 0;
$deckCount = 0;
$recent = [];
$snapshotLoaded = false;

// Webspace 1.1.0 stores the cross-device app state in account_sync_payloads.
// Prefer that snapshot for dashboard metrics. Existing 1.0.0 installs fall
// back to the original normalized collection/deck tables until the new sync
// endpoint has been used at least once.
try {
    $stmt = $pdo->prepare('SELECT payload FROM account_sync_payloads WHERE user_id = ? LIMIT 1');
    $stmt->execute([$user['id']]);
    $rawPayload = $stmt->fetchColumn();
    if (is_string($rawPayload) && $rawPayload !== '') {
        $snapshot = json_decode($rawPayload, true);
        if (is_array($snapshot)) {
            $rows = is_array($snapshot['collection'] ?? null) ? $snapshot['collection'] : [];
            $deckRows = is_array($snapshot['decks'] ?? null) ? $snapshot['decks'] : [];
            $collectionCount = count($rows);
            $deckCount = count($deckRows);
            foreach ($rows as $row) {
                if (!is_array($row)) continue;
                $totalCards += max(0, (int)($row['quantity'] ?? 0));
            }
            usort($rows, static fn(array $a, array $b): int =>
                ((int)($b['updated_at_ms'] ?? 0)) <=> ((int)($a['updated_at_ms'] ?? 0))
            );
            foreach (array_slice($rows, 0, 8) as $row) {
                if (!is_array($row)) continue;
                $recent[] = [
                    'card_name' => (string)($row['card_name'] ?? 'Karte'),
                    'set_code' => (string)($row['set_code'] ?? ''),
                    'rarity' => (string)($row['rarity'] ?? ''),
                    'quantity' => max(0, (int)($row['quantity'] ?? 0)),
                ];
            }
            $snapshotLoaded = true;
        }
    }
} catch (Throwable $e) {
    // account_sync_payloads is created lazily by /api/v1/sync.php on upgrades.
}

if (!$snapshotLoaded) {
    $stmt = $pdo->prepare('SELECT COUNT(*) FROM collection_items WHERE user_id = ? AND deleted_at IS NULL');
    $stmt->execute([$user['id']]);
    $collectionCount = (int)$stmt->fetchColumn();

    $stmt = $pdo->prepare('SELECT COALESCE(SUM(quantity),0) FROM collection_items WHERE user_id = ? AND deleted_at IS NULL');
    $stmt->execute([$user['id']]);
    $totalCards = (int)$stmt->fetchColumn();

    $stmt = $pdo->prepare('SELECT COUNT(*) FROM decks WHERE user_id = ? AND deleted_at IS NULL');
    $stmt->execute([$user['id']]);
    $deckCount = (int)$stmt->fetchColumn();

    $stmt = $pdo->prepare(
        'SELECT card_name, set_code, rarity, quantity, updated_at
         FROM collection_items
         WHERE user_id = ? AND deleted_at IS NULL
         ORDER BY updated_at DESC LIMIT 8'
    );
    $stmt->execute([$user['id']]);
    $recent = $stmt->fetchAll();
}

$stmt = $pdo->prepare('SELECT COUNT(*) FROM api_tokens WHERE user_id = ? AND revoked_at IS NULL AND expires_at > NOW()');
$stmt->execute([$user['id']]);
$deviceCount = (int)$stmt->fetchColumn();

$pageTitle = 'Dashboard';
require __DIR__ . '/includes/header.php';
?>
<section class="dashboard">
<div class="container">
  <div class="dashboard-head">
    <div>
      <span class="eyebrow">● Account aktiv</span>
      <h1 style="margin-bottom:6px">Hallo, <?= e($user['display_name'] ?: $user['username']) ?></h1>
      <div class="subtle">Hier siehst du die serverseitig gespeicherten Just-InCard-Daten deines Kontos.</div>
    </div>
    <a class="btn" href="account.php">Konto verwalten</a>
  </div>
  <?php if (isset($_GET['welcome'])): ?><div class="alert alert-ok">Dein Just-InCard-Konto wurde erstellt.</div><?php endif; ?>
  <div class="dashboard-grid">
    <div class="panel metric"><span>Sammlungseinträge</span><strong><?= $collectionCount ?></strong></div>
    <div class="panel metric"><span>Karten gesamt</span><strong><?= $totalCards ?></strong></div>
    <div class="panel metric"><span>Decks</span><strong><?= $deckCount ?></strong></div>
    <div class="panel metric"><span>aktive App-Tokens</span><strong><?= $deviceCount ?></strong></div>
  </div>
  <div class="wide-grid">
    <div class="panel card-panel">
      <h3>Zuletzt geänderte Sammlung</h3>
      <?php if (!$recent): ?>
        <p class="subtle">Noch keine Sammlung synchronisiert. Sobald Windows oder Android angebunden ist, erscheinen hier die letzten Änderungen.</p>
      <?php else: ?>
        <div class="table-wrap"><table class="table">
          <thead><tr><th>Karte</th><th>Set</th><th>Seltenheit</th><th>Menge</th></tr></thead>
          <tbody>
          <?php foreach ($recent as $row): ?>
            <tr><td><?= e($row['card_name'] ?: 'Karte') ?></td><td><?= e($row['set_code']) ?></td><td><?= e($row['rarity']) ?></td><td><?= (int)$row['quantity'] ?></td></tr>
          <?php endforeach; ?>
          </tbody>
        </table></div>
      <?php endif; ?>
    </div>
    <div class="panel card-panel">
      <h3>Synchronisationsprinzip</h3>
      <div class="list">
        <div class="list-item"><span>Windows</span><span class="badge">HTTPS API</span></div>
        <div class="list-item"><span>Android</span><span class="badge">HTTPS API</span></div>
        <div class="list-item"><span>Kartenbilder</span><span class="badge">nur Endgerät</span></div>
        <div class="list-item"><span>Sammlung & Decks</span><span class="badge">Server</span></div>
      </div>
    </div>
  </div>
</div>
</section>
<?php require __DIR__ . '/includes/footer.php'; ?>
