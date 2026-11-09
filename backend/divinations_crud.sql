-- =============================================================================
-- divinations 表：盘面 + 答案结构化存储
-- 对应参考文件 E:\workspace\aa\server.py 里的 CREATE_DIVINATION
-- =============================================================================

USE `divination_simple`;

-- -----------------------------------------------------------------------------
-- 建表（后端启动时也会自动执行，这里方便手工建表/查看）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `divinations` (
  `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `user_id` VARCHAR(64) NULL COMMENT '本项目存用户名，参考项目存用户ID字符串',
  `method` VARCHAR(16) NULL COMMENT '占卜方式：tarot/liuyao/bazi/...',
  `topic` VARCHAR(32) NULL COMMENT '问题主题：情感/事业/成长/抉择',
  `question` TEXT NULL COMMENT '所问之事',
  `board_text` MEDIUMTEXT NULL COMMENT '盘面文本/JSON：牌面、卦象、命盘等',
  `answer` MEDIUMTEXT NULL COMMENT '解读答案',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX `idx_user` (`user_id`),
  INDEX `idx_time` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- 查
-- -----------------------------------------------------------------------------
SELECT id, user_id, method, topic, question, created_at
FROM divinations
ORDER BY id DESC
LIMIT 20;

SELECT id, user_id, method, topic, question, board_text, answer, created_at
FROM divinations
WHERE user_id = 'demo'
ORDER BY id DESC;

-- -----------------------------------------------------------------------------
-- 增（手工插入一条示例；实际项目通过 POST /api/divinations 写入）
-- -----------------------------------------------------------------------------
INSERT INTO divinations (user_id, method, topic, question, board_text, answer)
VALUES (
  'demo',
  'tarot',
  '事业',
  '今年适合换工作吗？',
  '{"cards":[{"position":"当下指引","name":"愚者","orientation":"正位"}],"spreadName":"单张指引"}',
  '这是一条示例解读。'
);

-- -----------------------------------------------------------------------------
-- 改
-- -----------------------------------------------------------------------------
UPDATE divinations
SET topic = '成长', answer = '更新后的解读'
WHERE id = 1;

-- -----------------------------------------------------------------------------
-- 删
-- -----------------------------------------------------------------------------
DELETE FROM divinations
WHERE id = 1;
