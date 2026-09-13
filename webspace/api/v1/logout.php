<?php
declare(strict_types=1);require __DIR__.'/_init.php';$t=api_bearer_token();if(!$t)json_response(['ok'=>false,'error'=>'unauthorized'],401);db()->prepare('UPDATE api_tokens SET revoked_at=NOW() WHERE token_hash=?')->execute([token_hash($t)]);json_response(['ok'=>true]);
