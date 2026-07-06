#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule

import extractor
import prompts
import reporter
from analyser import stream_analyse
from mobsf_client import MobSFClient
from providers import build_provider

load_dotenv()
console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="Analyse an Android APK using MobSF + AI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Providers:
  ollama      Local via Ollama          (offline)
  lmstudio    Local via LM Studio       (offline)
  claude      Anthropic Claude          (requires API key)
  openai      OpenAI / ChatGPT          (requires API key)
  gemini      Google Gemini             (requires API key)

Examples:
  python main.py app.apk
  python main.py app.apk --provider claude --model claude-opus-4-8
  python main.py app.apk --provider ollama --model llama3.3:70b
  python main.py --report existing_report.json --provider gemini
        """,
    )
    parser.add_argument("apk", nargs="?", help="Path to the .apk file")
    parser.add_argument("--report", help="Use an existing MobSF JSON report instead of scanning")
    parser.add_argument(
        "--provider",
        default=os.getenv("PROVIDER", "ollama"),
        help="AI provider (default: ollama)",
    )
    parser.add_argument("--model", default=None, help="Model override for chosen provider")
    parser.add_argument("--mobsf-url", default=os.getenv("MOBSF_URL", "http://localhost:8000"))
    parser.add_argument("--mobsf-key", default=os.getenv("MOBSF_API_KEY", ""))
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", "http://localhost:11434"))
    parser.add_argument("--lmstudio-url", default=os.getenv("LM_STUDIO_URL", "http://localhost:1234"))
    parser.add_argument("--language", default=os.getenv("REPORT_LANGUAGE", "British English"), help="Language for the AI-generated report (default: British English)")
    parser.add_argument("--output-dir", default=".", help="Directory to save the report")
    parser.add_argument("--save-raw", action="store_true", help="Also save the raw MobSF JSON")
    args = parser.parse_args()

    if not args.apk and not args.report:
        parser.print_help()
        sys.exit(1)

    console.print(Panel.fit("[bold]APK Security Analyser[/bold]", subtitle="MobSF + AI"))

    # Build provider early so config errors surface before scanning
    env = dict(os.environ)
    if args.ollama_url:
        env["OLLAMA_URL"] = args.ollama_url
    if args.lmstudio_url:
        env["LM_STUDIO_URL"] = args.lmstudio_url

    try:
        provider = build_provider(args.provider, args.model, env)
    except ValueError as e:
        console.print(f"[red]Provider error:[/red] {e}")
        sys.exit(1)

    console.print(f"[cyan]Provider:[/cyan] {provider.name} / [bold]{provider.model}[/bold]")

    # --- MobSF scan or load existing report ---
    raw_report = None

    if args.report:
        console.print(f"[cyan]Loading report:[/cyan] {args.report}")
        raw_report = json.loads(Path(args.report).read_text())
    else:
        if not args.mobsf_key:
            console.print("[red]Error:[/red] MOBSF_API_KEY not set. Add it to .env or pass --mobsf-key")
            sys.exit(1)

        console.print(f"[cyan]APK:[/cyan] {args.apk}")
        console.print(f"[cyan]MobSF:[/cyan] {args.mobsf_url}")

        client = MobSFClient(args.mobsf_url, args.mobsf_key)

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
            task = progress.add_task("Uploading and scanning APK...", total=None)
            try:
                raw_report = client.upload_and_scan(args.apk)
                progress.update(task, description="[green]Scan complete.[/green]")
            except Exception as e:
                console.print(f"[red]MobSF error:[/red] {e}")
                sys.exit(1)

    if args.save_raw:
        raw_path = Path(args.output_dir) / "mobsf_raw.json"
        raw_path.write_text(json.dumps(raw_report, indent=2))
        console.print(f"[dim]Raw report saved to {raw_path}[/dim]")

    # --- Extract key findings ---
    console.print("\n[cyan]Extracting key findings...[/cyan]")
    extracted = extractor.extract(raw_report)

    app = extracted["app"]
    score = extracted["security_score"]
    console.print(f"  App:                  [bold]{app['name']}[/bold] ({app['package']})")
    console.print(f"  Version:              {app['version']}")
    console.print(f"  Security score:       [bold]{score}/100[/bold]")
    console.print(f"  Dangerous permissions:{len(extracted['dangerous_permissions'])}")
    console.print(f"  Trackers detected:    {len(extracted['trackers'])}")
    console.print(f"  Domains:              {extracted['network']['domains']['count']}")
    console.print(f"  Secrets found:        {len(extracted['secrets'])}")

    # --- AI analysis ---
    console.print(f"\n[cyan]Analysing...[/cyan]")
    console.print(Rule())

    prompt = prompts.build_analysis_prompt(extracted, language=args.language)
    ai_output = []

    try:
        for chunk in stream_analyse(prompt, provider):
            console.print(chunk, end="")
            ai_output.append(chunk)
    except Exception as e:
        console.print(f"\n[red]{provider.name} error:[/red] {e}")
        if provider.name in ("ollama", "lmstudio"):
            console.print(f"[dim]Is {provider.name} running?[/dim]")
        sys.exit(1)

    console.print("\n")
    console.print(Rule())

    # --- Save report ---
    full_report = "".join(ai_output)
    app_info = {**extracted["app"], "security_score": score, "average_cvss": extracted["average_cvss"]}
    report_path = reporter.save_report(app_info, full_report, args.output_dir)

    console.print(f"\n[green]Report saved:[/green] {report_path}")
    console.print(f"[green]Markdown:[/green]     {report_path.replace('.html', '.md')}")


if __name__ == "__main__":
    main()
