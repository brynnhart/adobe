from rich.console import Console
console = Console()
def info(msg: str): console.log(f"[bold cyan]INFO[/] {msg}")
def warn(msg: str): console.log(f"[bold yellow]WARN[/] {msg}")
def error(msg: str): console.log(f"[bold red]ERROR[/] {msg}")
