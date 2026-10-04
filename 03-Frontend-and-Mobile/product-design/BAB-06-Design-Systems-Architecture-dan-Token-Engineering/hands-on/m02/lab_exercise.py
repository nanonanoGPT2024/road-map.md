import json
import re
import sys
import time
from collections import defaultdict

# ANSI Escape Codes for Terminal UI
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Sample Raw Design Tokens with nested structures and references
RAW_TOKENS_JSON = """
{
  "color": {
    "base": {
      "blue": { "value": "#0066cc" },
      "red": { "value": "#ff0000" },
      "white": { "value": "#ffffff" },
      "black": { "value": "#000000" }
    },
    "brand": {
      "primary": { "value": "{color.base.blue}" },
      "danger": { "value": "{color.base.red}" }
    },
    "text": {
      "primary": { "value": "{color.base.black}" },
      "inverse": { "value": "{color.base.white}" }
    }
  },
  "spacing": {
    "small": { "value": "4px" },
    "medium": { "value": "8px" },
    "large": { "value": "16px" }
  },
  "components": {
    "button": {
      "background": { "value": "{color.brand.primary}" },
      "text": { "value": "{color.text.inverse}" },
      "padding": { "value": "{spacing.medium}" }
    }
  }
}
"""

class TokenEngine:
    def __init__(self, raw_json):
        self.raw_data = json.loads(raw_json)
        self.flat_tokens = {}
        self.resolved_tokens = {}
        
    def flatten(self, d, parent_key='', sep='.'):
        """Flattens nested dictionary into a single level dictionary with dot notation keys"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict) and "value" not in v:
                items.extend(self.flatten(v, new_key, sep=sep).items())
            elif isinstance(v, dict) and "value" in v:
                items.append((new_key, str(v["value"])))
        return dict(items)
        
    def resolve_reference(self, value, path_history):
        """Recursively resolves token references like {color.base.blue}"""
        # Regex to find references inside curly braces
        pattern = re.compile(r'\{([^{}]+)\}')
        matches = pattern.findall(value)
        
        if not matches:
            return value
            
        resolved_value = value
        for match in matches:
            if match in path_history:
                raise ValueError(f"Cyclic dependency detected: {' -> '.join(path_history)} -> {match}")
                
            if match not in self.flat_tokens:
                raise KeyError(f"Reference '{match}' not found in tokens.")
                
            # Recursive resolution
            ref_value = self.resolve_reference(self.flat_tokens[match], path_history + [match])
            resolved_value = resolved_value.replace(f"{{{match}}}", ref_value)
            
        return resolved_value

    def build(self):
        print(f"{Colors.HEADER}{Colors.BOLD}--- Starting Token Compilation Pipeline ---{Colors.ENDC}")
        time.sleep(0.5)
        
        print(f"{Colors.OKCYAN}[1/3] Flattening nested token structure...{Colors.ENDC}")
        self.flat_tokens = self.flatten(self.raw_data)
        print(f"      Found {len(self.flat_tokens)} raw tokens.")
        time.sleep(0.5)
        
        print(f"{Colors.OKCYAN}[2/3] Resolving token references...{Colors.ENDC}")
        for key, val in self.flat_tokens.items():
            try:
                resolved = self.resolve_reference(val, [key])
                self.resolved_tokens[key] = resolved
            except Exception as e:
                print(f"{Colors.FAIL}Error resolving token '{key}': {e}{Colors.ENDC}")
                sys.exit(1)
        print(f"      Successfully resolved all aliases.")
        time.sleep(0.5)
        
        print(f"{Colors.OKCYAN}[3/3] Generating output formats...{Colors.ENDC}")
        css_output = ":root {\\n"
        for k, v in self.resolved_tokens.items():
            css_var = f"--{k.replace('.', '-')}"
            css_output += f"  {css_var}: {v};\\n"
        css_output += "}"
        
        print(f"{Colors.OKGREEN}{Colors.BOLD}\\n--- Compilation Successful! ---{Colors.ENDC}")
        return css_output

def simulate_pipeline():
    print(f"{Colors.WARNING}Loading Design Tokens from Virtual File System...{Colors.ENDC}\\n")
    engine = TokenEngine(RAW_TOKENS_JSON)
    
    start_time = time.time()
    css_result = engine.build()
    end_time = time.time()
    
    print(f"\\n{Colors.BOLD}Generated CSS Variables:{Colors.ENDC}")
    print(css_result)
    print(f"\\n{Colors.WARNING}Pipeline completed in {((end_time - start_time)*1000):.2f} ms.{Colors.ENDC}")

if __name__ == "__main__":
    try:
        simulate_pipeline()
    except KeyboardInterrupt:
        print("\\nPipeline aborted by user.")
        sys.exit(0)
