SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(32) NOT NULL UNIQUE,
  email VARCHAR(190) NOT NULL UNIQUE,
  display_name VARCHAR(80) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('user','admin') NOT NULL DEFAULT 'user',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS api_tokens (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  token_hash CHAR(64) NOT NULL UNIQUE,
  device_name VARCHAR(120) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL,
  last_used_at DATETIME NULL,
  expires_at DATETIME NOT NULL,
  revoked_at DATETIME NULL,
  CONSTRAINT fk_tokens_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_tokens_user (user_id), INDEX idx_tokens_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS login_attempts (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  identity VARCHAR(190) NOT NULL,
  ip_address VARCHAR(64) NOT NULL,
  success TINYINT(1) NOT NULL DEFAULT 0,
  attempted_at DATETIME NOT NULL,
  INDEX idx_attempts_time (attempted_at), INDEX idx_attempts_identity (identity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS collection_items (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  sync_id VARCHAR(64) NOT NULL,
  external_id VARCHAR(120) NOT NULL DEFAULT '',
  card_id VARCHAR(64) NOT NULL DEFAULT '',
  card_name VARCHAR(255) NOT NULL DEFAULT '',
  set_code VARCHAR(80) NOT NULL DEFAULT '',
  rarity VARCHAR(120) NOT NULL DEFAULT '',
  language_code VARCHAR(16) NOT NULL DEFAULT '',
  card_condition VARCHAR(80) NOT NULL DEFAULT '',
  quantity INT UNSIGNED NOT NULL DEFAULT 0,
  added_at DATETIME NULL,
  updated_at DATETIME NOT NULL,
  deleted_at DATETIME NULL,
  revision BIGINT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT fk_collection_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE KEY uq_collection_sync (user_id, sync_id),
  INDEX idx_collection_updated (user_id, updated_at), INDEX idx_collection_card (user_id, card_id), INDEX idx_collection_set (user_id, set_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS decks (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  sync_id VARCHAR(64) NOT NULL,
  name VARCHAR(120) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  deleted_at DATETIME NULL,
  revision BIGINT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT fk_decks_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE KEY uq_deck_sync (user_id, sync_id), INDEX idx_decks_updated (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS deck_cards (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  deck_id BIGINT UNSIGNED NOT NULL,
  sync_id VARCHAR(64) NOT NULL,
  card_id VARCHAR(64) NOT NULL DEFAULT '',
  card_name VARCHAR(255) NOT NULL DEFAULT '',
  set_code VARCHAR(80) NOT NULL DEFAULT '',
  quantity INT UNSIGNED NOT NULL DEFAULT 0,
  section_name ENUM('MAIN','EXTRA','SIDE') NOT NULL DEFAULT 'MAIN',
  sort_order INT UNSIGNED NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  deleted_at DATETIME NULL,
  CONSTRAINT fk_deck_cards_deck FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE,
  UNIQUE KEY uq_deck_card_sync (deck_id, sync_id), INDEX idx_deck_cards_section (deck_id, section_name, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS account_sync_payloads (
  user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
  revision BIGINT UNSIGNED NOT NULL DEFAULT 0,
  schema_name VARCHAR(80) NOT NULL DEFAULT 'justincard-account-sync-v1',
  source_device VARCHAR(120) NOT NULL DEFAULT '',
  payload MEDIUMTEXT NOT NULL,
  updated_at DATETIME NOT NULL,
  CONSTRAINT fk_account_sync_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
