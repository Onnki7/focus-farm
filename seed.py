"""
seed.py — 演示数据生成器
Focus Farm 项目演示用种子数据

使用方法：
    python seed.py

效果：
    - 创建 3 个演示账号（demo / alice / bob）
    - demo 账号：12次已完成会话，横跨14天，已解锁12块农场地块
    - alice 账号：8次已完成会话，已解锁8块地块
    - bob 账号：3次已完成会话，已解锁3块地块
    - 3人共同加入同一个演示小队（分享码：FARM-DEMO）
    - alice 有一个正在进行中的会话（演示小队实时进度）

注意：
    - 如果账号已存在会跳过，不会重复创建
    - 可以重复运行，不会出错
    - 删除 focus_farm.db 后重新运行可完全重置

演示账号密码：
    demo  / demo1234
    alice / alice123
    bob   / bob12345
"""

import sys
import os
import json
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta

# 确保能找到 core 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ── 配置 ──────────────────────────────────────────────────────────────────────
DB_PATH = 'focus_farm.db'

DEMO_USERS = [
    {'username': 'demo',  'password': 'demo1234',  'sessions': 12, 'label': '主演示账号'},
    {'username': 'alice', 'password': 'alice123',  'sessions': 8,  'label': '小队成员A'},
    {'username': 'bob',   'password': 'bob12345',  'sessions': 3,  'label': '小队成员B'},
]

SQUAD_CODE = 'FARM-DEMO'
SQUAD_NAME = '演示小队'

# 20种地块名称（用于日志输出）
TILE_NAMES = [
    '土地', '幼苗', '庄稼', '麦田', '栅栏', '谷仓', '水井', '池塘',
    '粮仓', '温室', '风车', '果园', '马厩', '蜂巢', '饮水槽', '市场',
    '小屋', '林地', '喷泉', '庄园'
]


# ── 工具函数 ──────────────────────────────────────────────────────────────────
def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode()).hexdigest()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return conn


def ensure_db():
    """确保数据库和所有表存在"""
    from core import config, db
    config.load()
    db.init_db()
    print('✅ 数据库初始化完成')


# ── 创建用户 ──────────────────────────────────────────────────────────────────
def create_user_if_not_exists(conn, username: str, password: str) -> int:
    """创建用户，若已存在则返回现有ID"""
    row = conn.execute(
        'SELECT id FROM users WHERE username=?', (username,)
    ).fetchone()

    if row:
        print(f'  ⏭  用户 [{username}] 已存在，跳过创建')
        return row['id']

    salt = secrets.token_hex(8)
    pwd_hash = hash_password(password, salt)
    now = datetime.utcnow().isoformat()

    conn.execute(
        'INSERT INTO users (username, password_hash, salt, created_at) VALUES (?,?,?,?)',
        (username, pwd_hash, salt, now)
    )
    conn.commit()
    user_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

    # 同时创建空农场
    conn.execute(
        'INSERT OR IGNORE INTO farms (user_id, tiles_json, total_tiles, updated_at) '
        'VALUES (?,?,?,?)',
        (user_id, '[]', 0, now)
    )
    conn.commit()

    print(f'  ✅ 用户 [{username}] 创建成功 (id={user_id})')
    return user_id


# ── 创建会话记录 ──────────────────────────────────────────────────────────────
def seed_sessions(conn, user_id: int, count: int, username: str):
    """
    为用户创建 count 条已完成会话，分布在过去14天内。
    同时更新农场地块解锁状态。
    """
    # 检查已有会话数
    existing = conn.execute(
        "SELECT COUNT(*) as n FROM sessions WHERE user_id=? AND status='completed'",
        (user_id,)
    ).fetchone()['n']

    if existing >= count:
        print(f'  ⏭  [{username}] 已有 {existing} 条完成记录，跳过会话创建')
        return

    to_create = count - existing
    print(f'  📝 [{username}] 创建 {to_create} 条会话记录...')

    # 获取当前农场状态
    farm = conn.execute(
        'SELECT tiles_json, total_tiles FROM farms WHERE user_id=?', (user_id,)
    ).fetchone()
    tiles = json.loads(farm['tiles_json'])
    start_tile = len(tiles)

    now = datetime.utcnow()

    for i in range(to_create):
        # 分布在过去14天，每天不同小时
        days_ago = 13 - (i * 13 // max(to_create - 1, 1))
        hour = 8 + (i * 3) % 12   # 在 8am~8pm 之间分布

        started = now - timedelta(days=days_ago) + timedelta(hours=hour - now.hour)
        started = started.replace(minute=0, second=0, microsecond=0)
        duration = 25  # 所有演示会话统一25分钟
        ended = started + timedelta(minutes=duration)
        completed = ended + timedelta(seconds=30)  # 完成时间略晚于结束时间

        tile_index = start_tile + i if (start_tile + i) < 20 else None

        conn.execute(
            '''INSERT INTO sessions
               (user_id, duration_mins, started_at, ends_at, completed_at, status, tile_unlocked)
               VALUES (?,?,?,?,?,?,?)''',
            (user_id, duration, started.isoformat(), ended.isoformat(),
             completed.isoformat(), 'completed', tile_index)
        )

        if tile_index is not None:
            tiles.append(tile_index)
            tile_name = TILE_NAMES[tile_index] if tile_index < len(TILE_NAMES) else f'地块{tile_index}'
            print(f'    🌾 第{start_tile + i + 1}次会话 → 解锁【{tile_name}】')

    # 更新农场
    conn.execute(
        'UPDATE farms SET tiles_json=?, total_tiles=?, updated_at=? WHERE user_id=?',
        (json.dumps(tiles), len(tiles), now.isoformat(), user_id)
    )
    conn.commit()
    print(f'  ✅ [{username}] 农场已更新，共 {len(tiles)} 块地块')


# ── 创建进行中的会话（用于演示小队实时进度）────────────────────────────────────
def seed_active_session(conn, user_id: int, username: str):
    """为用户创建一个正在进行中的会话（用于演示小队实时进度条）"""
    existing = conn.execute(
        "SELECT id FROM sessions WHERE user_id=? AND status='active'",
        (user_id,)
    ).fetchone()

    if existing:
        print(f'  ⏭  [{username}] 已有活跃会话，跳过')
        return

    now = datetime.utcnow()
    started = now - timedelta(minutes=8)    # 8分钟前开始
    ends_at = now + timedelta(minutes=17)   # 还有17分钟结束（共25分钟）

    conn.execute(
        '''INSERT INTO sessions
           (user_id, duration_mins, started_at, ends_at, status)
           VALUES (?,?,?,?,?)''',
        (user_id, 25, started.isoformat(), ends_at.isoformat(), 'active')
    )
    conn.commit()
    print(f'  🔴 [{username}] 创建活跃会话（进行中，已专注8分钟，剩余17分钟）')


# ── 创建小队 ──────────────────────────────────────────────────────────────────
def seed_squad(conn, user_ids: list, usernames: list):
    """创建演示小队并将所有用户加入"""
    existing = conn.execute(
        'SELECT id FROM squads WHERE code=?', (SQUAD_CODE,)
    ).fetchone()

    if existing:
        squad_id = existing['id']
        print(f'  ⏭  小队 [{SQUAD_CODE}] 已存在')
    else:
        now = datetime.utcnow().isoformat()
        conn.execute(
            'INSERT INTO squads (code, name, created_by, created_at) VALUES (?,?,?,?)',
            (SQUAD_CODE, SQUAD_NAME, user_ids[0], now)
        )
        conn.commit()
        squad_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        print(f'  ✅ 小队 [{SQUAD_NAME}] 创建成功 (code={SQUAD_CODE})')

    # 将所有用户加入小队
    now = datetime.utcnow().isoformat()
    for uid, uname in zip(user_ids, usernames):
        existing_member = conn.execute(
            'SELECT 1 FROM squad_members WHERE user_id=?', (uid,)
        ).fetchone()

        if existing_member:
            print(f'  ⏭  [{uname}] 已在小队中')
        else:
            conn.execute(
                'INSERT OR REPLACE INTO squad_members (squad_id, user_id, joined_at) '
                'VALUES (?,?,?)',
                (squad_id, uid, now)
            )
            conn.commit()
            print(f'  ✅ [{uname}] 已加入小队')


# ── 主函数 ────────────────────────────────────────────────────────────────────
def main():
    print()
    print('=' * 55)
    print('  Focus Farm — 演示数据生成器')
    print('=' * 55)
    print()

    # 初始化数据库
    ensure_db()
    print()

    conn = get_conn()
    user_ids = []
    usernames = []

    # 创建用户 + 会话数据
    for user_cfg in DEMO_USERS:
        print(f'👤 处理用户：{user_cfg["username"]} （{user_cfg["label"]}）')
        uid = create_user_if_not_exists(
            conn, user_cfg['username'], user_cfg['password']
        )
        seed_sessions(conn, uid, user_cfg['sessions'], user_cfg['username'])
        user_ids.append(uid)
        usernames.append(user_cfg['username'])
        print()

    # alice 创建一个活跃会话，用于演示小队实时进度
    print('🔴 创建演示用活跃会话（小队进度条演示）：')
    seed_active_session(conn, user_ids[1], 'alice')
    print()

    # 创建小队
    print('👥 创建演示小队：')
    seed_squad(conn, user_ids, usernames)
    print()

    conn.close()

    # 输出演示说明
    print('=' * 55)
    print('  演示数据生成完成！')
    print('=' * 55)
    print()
    print('  演示账号信息：')
    print()
    print('  ┌──────────┬──────────┬───────────────────────┐')
    print('  │ 用户名   │ 密码     │ 状态                  │')
    print('  ├──────────┼──────────┼───────────────────────┤')
    print('  │ demo     │ demo1234 │ 12次会话，12块地块     │')
    print('  │ alice    │ alice123 │ 8次会话，专注进行中    │')
    print('  │ bob      │ bob12345 │ 3次会话，3块地块       │')
    print('  └──────────┴──────────┴───────────────────────┘')
    print()
    print('  小队分享码：FARM-DEMO')
    print()
    print('  演示建议：')
    print('  1. 用 demo 账号登录 → 查看农场（12块地块）')
    print('  2. 查看 Focus 标签 → 14天趋势图和诚实报告')
    print('  3. 查看 Awards 标签 → 已解锁成就')
    print('  4. 查看 Squad 标签 → alice 正在专注中（进度条）')
    print('  5. 查看 Log 标签 → 会话历史，点击导出CSV')
    print('  6. 完成一次会话 → 演示新地块解锁动画')
    print()
    print('  运行方式：')
    print('  python app.py → 浏览器打开 http://localhost:5000')
    print()


if __name__ == '__main__':
    main()
