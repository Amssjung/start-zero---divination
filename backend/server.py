"""数据库工具模块。

只提供 get_conn / init_db / get_user_id / escape 这些函数，供 web_app.py 导入。
网页端统一走 web_app.py 的 HTTP 接口（默认 8000 端口）。
早期基于 socket 的 TCP 服务（8888）已经废弃并移除。

表结构：
    users        用户账号（username / display_name / password_hash）
    history      一次占卜的展示记录（question / method / hexagram / result）
    divinations  结构化记录（board_text / answer），供统计与回看
"""
import pymysql

import os

DB_HOST = os.getenv("XINGXUN_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("XINGXUN_DB_PORT", "3306"))
DB_USER = os.getenv("XINGXUN_DB_USER", "root")
DB_PASSWORD = os.getenv("XINGXUN_DB_PASSWORD", "")
DB_NAME = os.getenv("XINGXUN_DB_NAME", "divination_simple")



def get_conn():
    """连接已经建好的数据库。"""
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4"
    )
    return conn


def init_db():
    """建库、建表；表已存在就跳过。"""
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        charset="utf8mb4"
    )
    cur = conn.cursor()

    cur.execute("CREATE DATABASE IF NOT EXISTS %s DEFAULT CHARSET utf8mb4" % DB_NAME)
    cur.execute("USE %s" % DB_NAME)

    cur.execute("SHOW TABLES LIKE 'users'")
    if cur.fetchone() is None:
        cur.execute(
            """CREATE TABLE users (
                id int unsigned primary key auto_increment,
                username varchar(100) not null unique,
                display_name varchar(100),
                password_hash varchar(64),
                created_at datetime default current_timestamp
            )"""
        )

    cur.execute("SHOW TABLES LIKE 'history'")
    if cur.fetchone() is None:
        cur.execute(
            """CREATE TABLE history (
                id int unsigned primary key auto_increment,
                user_id int unsigned not null,
                question text not null,
                method varchar(20) default 'liuyao',
                hexagram varchar(100),
                result text,
                created_at datetime default current_timestamp
            )"""
        )

    # 新增产品库表：把盘面、答案等结构化字段单独存一张表
    # 参考 E:\workspace\aa\server.py 里的 CREATE_DIVINATION
    cur.execute(
        """CREATE TABLE IF NOT EXISTS divinations (
            id bigint unsigned primary key auto_increment,
            user_id varchar(64),
            method varchar(16),
            topic varchar(32),
            question text,
            board_text mediumtext,
            answer mediumtext,
            created_at timestamp default current_timestamp,
            index idx_user (user_id),
            index idx_time (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
    )

    conn.commit()
    cur.close()
    conn.close()


def escape(text):
    """把单引号变成两个，避免 SQL 字符串被截断。"""
    return text.replace("'", "''")


def get_user_id(cur, username):
    """用户不存在就插入，最后返回 users.id。"""
    cur.execute("SELECT id FROM users WHERE username = '%s'" % escape(username))
    row = cur.fetchone()
    if row is None:
        cur.execute("INSERT INTO users (username) VALUES ('%s')" % escape(username))
        cur.execute("SELECT id FROM users WHERE username = '%s'" % escape(username))
        row = cur.fetchone()
    return row[0]
