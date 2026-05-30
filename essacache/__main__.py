import asyncio
import argparse
import logging
from .server import EssaCacheServer

def main():
    parser = argparse.ArgumentParser(description="EssaCache - A Redis Clone in Python")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=6379, help="Port to bind to")
    parser.add_argument("--capacity", type=int, default=10000, help="LRU Cache capacity")
    parser.add_argument("--aof", type=str, default="essacache.aof", help="Path to AOF file")
    parser.add_argument("--rdb", type=str, default="essacache.rdb", help="Path to RDB snapshot file")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    
    server = EssaCacheServer(host=args.host, port=args.port, capacity=args.capacity, aof_path=args.aof, rdb_path=args.rdb)
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logging.info("Shutting down EssaCache...")

if __name__ == "__main__":
    main()
