-- =============================================================================
-- 用户信息 CRUD 示例
-- 数据库：divination_simple
-- 用法：在 PyCharm 的 Database 控制台里打开 divination_simple，然后逐段执行
-- =============================================================================

USE `divination_simple`;

-- -----------------------------------------------------------------------------
-- 查：看所有用户 / 看总数
-- -----------------------------------------------------------------------------
SELECT id, username, display_name, created_at
FROM users
ORDER BY id;

SELECT COUNT(*) AS total FROM users;

-- -----------------------------------------------------------------------------
-- 增：新增一个用户
-- password_hash 和后端一样用 SHA-256（MySQL 的 SHA2(..., 256) 结果一致）
-- 实际注册请走页面 / POST /api/register，这里只用于练习或手工补数据
-- -----------------------------------------------------------------------------
INSERT INTO users (username, display_name, password_hash)
VALUES ('test_user', '测试用户', SHA2('123456', 256));

-- 查刚插入的那条
SELECT id, username, display_name, created_at
FROM users
WHERE username = 'test_user';

-- -----------------------------------------------------------------------------
-- 改：改昵称 / 改密码
-- -----------------------------------------------------------------------------
UPDATE users
SET display_name = '新昵称'
WHERE username = 'test_user';

UPDATE users
SET password_hash = SHA2('newpass123', 256)
WHERE username = 'test_user';

-- -----------------------------------------------------------------------------
-- 删：先删这个用户的历史记录，再删用户
-- （history.user_id 没有外键，直接删用户会留下孤儿记录）
-- -----------------------------------------------------------------------------
DELETE FROM history
WHERE user_id = (SELECT id FROM users WHERE username = 'test_user');

DELETE FROM users
WHERE username = 'test_user';

-- 删除后确认
SELECT id, username, display_name, created_at
FROM users
ORDER BY id;
