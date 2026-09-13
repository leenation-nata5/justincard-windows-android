<?php
declare(strict_types=1);
function current_user(): ?array {
    if(empty($_SESSION['user_id'])) return null;
    $q=db()->prepare('SELECT id,username,email,display_name,role,created_at FROM users WHERE id=? AND is_active=1 LIMIT 1');$q->execute([(int)$_SESSION['user_id']]);return $q->fetch()?:null;
}
function require_user(): array { $u=current_user(); if(!$u){header('Location: login.php');exit;} return $u; }
function api_bearer_token(): ?string {
    $h=$_SERVER['HTTP_AUTHORIZATION']??'';
    if(!$h && function_exists('getallheaders')){$a=getallheaders();$h=$a['Authorization']??$a['authorization']??'';}
    return preg_match('/^Bearer\s+(.+)$/i',trim($h),$m)?trim($m[1]):null;
}
function api_user(): array {
    $t=api_bearer_token(); if(!$t) json_response(['ok'=>false,'error'=>'unauthorized'],401);
    $q=db()->prepare('SELECT u.id,u.username,u.email,u.display_name,u.role FROM api_tokens t JOIN users u ON u.id=t.user_id WHERE t.token_hash=? AND t.revoked_at IS NULL AND t.expires_at>NOW() AND u.is_active=1 LIMIT 1');
    $q->execute([token_hash($t)]);$u=$q->fetch(); if(!$u) json_response(['ok'=>false,'error'=>'invalid_token'],401);
    db()->prepare('UPDATE api_tokens SET last_used_at=NOW() WHERE token_hash=?')->execute([token_hash($t)]); return $u;
}
function issue_api_token(int $userId,string $device=''): string {
    global $config; $t=random_token(32);$days=max(1,(int)($config['security']['token_ttl_days']??90));
    $q=db()->prepare("INSERT INTO api_tokens(user_id,token_hash,device_name,created_at,expires_at) VALUES(?,?,?,NOW(),DATE_ADD(NOW(),INTERVAL {$days} DAY))");$q->execute([$userId,token_hash($t),substr($device,0,120)]);return $t;
}
