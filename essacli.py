#!/usr/bin/env python3
import socket
import argparse
import sys
import shlex
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.text import Text

from essacache.resp import RESPDecoder

console = Console()

COMMANDS = [
    "PING", "SET", "GET", "DEL", "EXISTS", "LPUSH", "RPUSH", "LPOP", "RPOP", "LRANGE",
    "HSET", "HGET", "HGETALL", "INCR", "DECR", "SAVE", "BGSAVE", "PUBLISH", "SUBSCRIBE",
    "UNSUBSCRIBE", "MULTI", "EXEC", "DISCARD", "KEYS", "QUIT", "CLEAR"
]

completer = WordCompleter(COMMANDS, ignore_case=True)

style = Style.from_dict({
    'prompt': 'bold ansiwhite',
    'host': 'bold ansicyan',
})

def encode_command(*args):
    parts = [f"*{len(args)}\r\n".encode('utf-8')]
    for arg in args:
        arg_bytes = str(arg).encode('utf-8')
        parts.append(f"${len(arg_bytes)}\r\n".encode('utf-8'))
        parts.append(arg_bytes)
        parts.append(b"\r\n")
    return b"".join(parts)

def format_response(response, depth=0):
    indent = "  " * depth
    if response is None:
        console.print(f"{indent}(nil)", style="italic grey50")
    elif isinstance(response, int):
        console.print(f"{indent}(integer) {response}", style="blue")
    elif isinstance(response, bytes):
        try:
            text = response.decode('utf-8')
            if depth > 0:
                console.print(f'"{text}"', style="green")
            else:
                console.print(f'"{text}"', style="green")
        except UnicodeDecodeError:
            console.print(f"(raw bytes) {response}", style="yellow")
    elif isinstance(response, str):
        if response.startswith("ERR") or response.startswith("WRONGTYPE"):
            console.print(f"{indent}(error) {response}", style="bold red")
        else:
            console.print(f"{indent}{response}", style="green")
    elif isinstance(response, list):
        if not response:
            console.print(f"{indent}(empty array)", style="italic grey50")
        else:
            for i, item in enumerate(response):
                prefix = f"{i+1}) "
                console.print(f"{indent}{prefix}", end="")
                format_response(item, depth + 1)
    elif isinstance(response, Exception):
        console.print(f"{indent}(error) {str(response)}", style="bold red")

def main():
    parser = argparse.ArgumentParser(description="EssaCache Interactive CLI")
    parser.add_argument("-H", "--host", dest="hostname", type=str, default="127.0.0.1", help="Server hostname")
    parser.add_argument("-p", "--port", type=int, default=6379, help="Server port")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((args.hostname, args.port))
    except Exception as e:
        console.print(f"[bold red]Could not connect to EssaCache at {args.hostname}:{args.port}[/bold red]\n{e}")
        sys.exit(1)

    decoder = RESPDecoder()
    session = PromptSession(completer=completer, style=style)
    
    prompt_text = [
        ('class:host', f"{args.hostname}:{args.port}"),
        ('class:prompt', '> ')
    ]

    console.print(f"[bold green]Connected to EssaCache at {args.hostname}:{args.port}[/bold green]")
    console.print("Type 'QUIT' to exit, 'CLEAR' to clear terminal.")

    while True:
        try:
            text = session.prompt(prompt_text)
            if not text.strip():
                continue
                
            try:
                # Use shlex to correctly parse quoted strings like PUBLISH channel "hello world"
                parts = shlex.split(text)
            except ValueError as e:
                console.print(f"[bold red]Invalid syntax:[/bold red] {e}")
                continue

            cmd_name = parts[0].upper()
            
            if cmd_name == "QUIT" or cmd_name == "EXIT":
                console.print("Bye!", style="bold cyan")
                break
            elif cmd_name == "CLEAR":
                console.clear()
                continue
                
            cmd_bytes = encode_command(*parts)
            sock.sendall(cmd_bytes)
            
            # If SUBSCRIBE, enter blocking read loop
            if cmd_name in ["SUBSCRIBE", "PSUBSCRIBE"]:
                console.print("Reading messages... (press Ctrl-C to quit)", style="italic yellow")
                try:
                    while True:
                        data = sock.recv(4096)
                        if not data:
                            console.print("[bold red]Connection closed by server.[/bold red]")
                            return
                        cmds = decoder.decode(data)
                        for cmd in cmds:
                            format_response(cmd)
                except KeyboardInterrupt:
                    # After Ctrl-C, reconnect to exit subscribed mode safely
                    console.print("\n[bold yellow]Subscription interrupted. Reconnecting to restore state...[/bold yellow]")
                    sock.close()
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((args.hostname, args.port))
                    continue

            # Standard synchronous read
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    console.print("[bold red]Connection closed by server.[/bold red]")
                    return
                data += chunk
                cmds = decoder.decode(data)
                if cmds:
                    for cmd in cmds:
                        format_response(cmd)
                    break
                    
        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            break

    sock.close()

if __name__ == "__main__":
    main()
