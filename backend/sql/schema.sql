-- 星询 · 数据库结构
-- 三张表：用户、展示记录、结构化记录

CREATE DATABASE IF NOT EXISTS divination_simple
    DEFAULT CHARSET utf8mb4;

USE divination_simple;

-- 用户
CREATE TABLE IF NOT EXISTS users (
    id            INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    username      VARCHAR(100) NOT NULL UNIQUE,
    display_name  VARCHAR(100),
    -- pbkdf2$ 前缀 + 64 位十六进制，共 71 字符；旧版 sha256 是 64 字符
    password_hash VARCHAR(128),
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 展示记录：一次占卜一行，给界面列表用
CREATE TABLE IF NOT EXISTS history (
    id         INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    user_id    INT UNSIGNED NOT NULL,          -- 指向 users.id
    question   TEXT NOT NULL,
    method     VARCHAR(20) DEFAULT 'liuyao',   -- tarot / liuyao / bazi / ...
    hexagram   VARCHAR(100),                   -- 卦名或牌阵名
    result     TEXT,                           -- 整条记录的 JSON 字符串
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_time (created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 结构化记录：字段拆开，方便 SQL 直接统计
CREATE TABLE IF NOT EXISTS divinations (
    id         BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    user_id    VARCHAR(64),                    -- 注意：这里是用户名，不是数字 id
    method     VARCHAR(16),
    topic      VARCHAR(32),                    -- marriage / matter / fortune / ...
    question   TEXT,
    board_text MEDIUMTEXT,                     -- 盘面：牌、卦象、命盘
    answer     MEDIUMTEXT,                     -- 模型生成的解读
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_time (created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
