import argparse, os
from .io.files import load_brief
from .pipeline import process_campaign

def main():
    parser = argparse.ArgumentParser(description='Creative Automation Pipeline (OpenAI CLI)')
    parser.add_argument('--brief', required=True, help='Path to brief YAML/JSON')
    parser.add_argument('--out', required=True, help='Output directory')
    parser.add_argument('--variants', type=int, default=None, help='Override count_per_product')
    args = parser.parse_args()

    brief = load_brief(args.brief)
    process_campaign(brief, args.out, variants_override=args.variants)

if __name__ == '__main__':
    main()
