"""客户关系管理系统（桌面版）启动入口。

用法：
    python main.py              # 使用默认数据文件 ~/.crm-desktop/crm.db
    python main.py --db my.db   # 指定数据文件
    python main.py --demo       # 首次体验：写入演示数据
"""
import argparse

from crm.app import default_db_path, main
from crm.db import Database
from crm.demo import load_demo_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="客户关系管理系统（桌面版）")
    parser.add_argument("--db", help="SQLite 数据文件路径")
    parser.add_argument("--demo", action="store_true", help="写入演示数据后启动")
    args = parser.parse_args()
    path = args.db or default_db_path()
    if args.demo:
        db = Database(path)
        load_demo_data(db)
        db.close()
    main(path)
