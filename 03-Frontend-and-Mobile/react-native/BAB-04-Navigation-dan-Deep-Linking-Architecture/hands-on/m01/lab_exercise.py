#!/usr/bin/env python3
"""
React Native Architecture Simulator: BAB-04 Navigation & Deep Linking Architecture
Simulasi komprehensif struktur Navigation State Tree, Stack/Tab Reducer, dan Deep Link Route Matcher.
"""

import sys
import re
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, parse_qs

# ANSI Terminal Colors
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    DIM = "\033[2m"
    RESET = "\033[0m"

@dataclass
class Route:
    name: str
    key: str
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class NavigationState:
    index: int
    routes: List[Route]
    type: str = "stack"  # "stack" or "tab"

class StackNavigator:
    def __init__(self, name: str, initial_route: str):
        self.name = name
        self.key_counter = 1
        initial = Route(name=initial_route, key=f"{initial_route}-{self.key_counter}")
        self.state = NavigationState(index=0, routes=[initial], type="stack")

    def _generate_key(self, route_name: str) -> str:
        self.key_counter += 1
        return f"{route_name}-{self.key_counter}"

    def push(self, name: str, params: Optional[Dict[str, Any]] = None) -> Route:
        route = Route(name=name, key=self._generate_key(name), params=params or {})
        self.state.routes.append(route)
        self.state.index = len(self.state.routes) - 1
        return route

    def pop(self) -> Optional[Route]:
        if len(self.state.routes) <= 1:
            return None
        popped = self.state.routes.pop()
        self.state.index = len(self.state.routes) - 1
        return popped

    def replace(self, name: str, params: Optional[Dict[str, Any]] = None) -> Route:
        route = Route(name=name, key=self._generate_key(name), params=params or {})
        self.state.routes[self.state.index] = route
        return route

    def reset(self, routes: List[Tuple[str, Dict[str, Any]]], index: Optional[int] = None):
        new_routes = [
            Route(name=r_name, key=self._generate_key(r_name), params=r_params)
            for r_name, r_params in routes
        ]
        self.state.routes = new_routes
        self.state.index = (len(new_routes) - 1) if index is None else index

class DeepLinkRouter:
    """
    Simulates React Navigation LinkingConfiguration path matching and state dispatch.
    """
    def __init__(self, prefixes: List[str], config: Dict[str, Any]):
        self.prefixes = prefixes
        self.config = config  # Map pattern -> route descriptor
        self.compiled_routes: List[Tuple[re.Pattern, str, List[str]]] = []
        self._compile_routes()

    def _compile_routes(self):
        for pattern, route_name in self.config.items():
            param_keys = re.findall(r":([a-zA-Z_0-9]+)", pattern)
            regex_pattern = "^" + re.sub(r":[a-zA-Z_0-9]+", r"([^/]+)", pattern) + "$"
            self.compiled_routes.append((re.compile(regex_pattern), route_name, param_keys))

    def resolve(self, uri: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        matched_prefix = None
        for prefix in self.prefixes:
            if uri.startswith(prefix):
                matched_prefix = prefix
                break

        if not matched_prefix:
            return None

        path_with_query = uri[len(matched_prefix):]
        if not path_with_query.startswith("/"):
            path_with_query = "/" + path_with_query

        parsed = urlparse("scheme://dummy" + path_with_query)
        path = parsed.path
        query_params = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query).items()}

        for regex, route_name, param_keys in self.compiled_routes:
            match = regex.match(path)
            if match:
                extracted_params = dict(zip(param_keys, match.groups()))
                extracted_params.update(query_params)
                return route_name, extracted_params

        return None

def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
======================================================================
  REACT NATIVE NAVIGATION & DEEP LINKING ARCHITECTURE SIMULATOR
  Bab 04: Navigation State Tree, Stack Dispatcher & Linking Engine
======================================================================{Colors.RESET}"""
    print(banner)

def render_navigation_tree(stack: StackNavigator):
    print(f"\n{Colors.BOLD}--- CURRENT NAVIGATION STATE TREE (Root Stack) ---{Colors.RESET}")
    print(f"Stack Depth : {Colors.YELLOW}{len(stack.state.routes)}{Colors.RESET} | Active Index: {Colors.GREEN}{stack.state.index}{Colors.RESET}")
    print(f"{Colors.DIM}['NavigationContainer' root]{Colors.RESET}")
    for idx, r in enumerate(stack.state.routes):
        is_active = (idx == stack.state.index)
        pointer = f"{Colors.GREEN}->{Colors.RESET}" if is_active else "  "
        badge = f"{Colors.BOLD}{Colors.GREEN}[ACTIVE SCREEN]{Colors.RESET}" if is_active else f"{Colors.DIM}[HISTORICAL STATE]{Colors.RESET}"
        params_str = json.dumps(r.params) if r.params else "{}"
        print(f"  {pointer} [Layer {idx}] {Colors.CYAN}{r.name:<18}{Colors.RESET} key={r.key} {badge}")
        if r.params:
            print(f"       {Colors.YELLOW}route.params{Colors.RESET}: {params_str}")
    print("--------------------------------------------------\n")

def run_simulation():
    print_banner()

    linking_config = {
        "/home": "HomeScreen",
        "/feed": "FeedScreen",
        "/product/:productId": "ProductDetailScreen",
        "/user/:userId/orders/:orderId": "OrderDetailScreen",
        "/settings/profile": "ProfileScreen"
    }
    prefixes = ["myapp://", "https://shop.myapp.com"]
    router = DeepLinkRouter(prefixes=prefixes, config=linking_config)
    stack = StackNavigator(name="RootStack", initial_route="HomeScreen")

    print(f"{Colors.BOLD}1. Konfigurasi Deep Linking React Navigation:{Colors.RESET}")
    print(f"   Registered Prefixes: {Colors.BLUE}{prefixes}{Colors.RESET}")
    print(f"   Path Mapping:")
    for pat, target in linking_config.items():
        print(f"     - {Colors.YELLOW}{pat:<32}{Colors.RESET} => {Colors.CYAN}{target}{Colors.RESET}")

    render_navigation_tree(stack)

    # Simulation steps
    print(f"{Colors.BOLD}2. Eksekusi Navigasi Standar (Stack Operations):{Colors.RESET}")
    
    print(f"\n[ACTION] dispatch(StackActions.push('FeedScreen', {{ category: 'electronics' }}))")
    stack.push("FeedScreen", {"category": "electronics"})
    render_navigation_tree(stack)

    print(f"[ACTION] dispatch(StackActions.push('ProductDetailScreen', {{ productId: 'prod-9901' }}))")
    stack.push("ProductDetailScreen", {"productId": "prod-9901"})
    render_navigation_tree(stack)

    print(f"[ACTION] dispatch(CommonActions.goBack())")
    popped = stack.pop()
    print(f"{Colors.RED}<< Layar Di-unmount (Popped): {popped.name} (key: {popped.key}){Colors.RESET}")
    render_navigation_tree(stack)

    print(f"{Colors.BOLD}3. Simulasi Resolusi Deep Linking Masuk (Cold/Warm Start):{Colors.RESET}")
    sample_incoming_links = [
        "myapp://product/prod-4421?ref=promo_october&discount=20",
        "https://shop.myapp.com/user/usr-888/orders/ord-9923?notify=true",
        "myapp://unregistered/resource/404",
        "invalid-scheme://product/prod-11"
    ]

    for link in sample_incoming_links:
        print(f"\nIncoming Intent/URI: {Colors.UNDERLINE}{link}{Colors.RESET}")
        result = router.resolve(link)
        if result:
            target_screen, params = result
            print(f"  {Colors.GREEN}[V] Match Found!{Colors.RESET}")
            print(f"      Resolved Screen : {Colors.CYAN}{Colors.BOLD}{target_screen}{Colors.RESET}")
            print(f"      Parsed Params   : {Colors.YELLOW}{json.dumps(params)}{Colors.RESET}")
            print(f"  --> Navigating to {target_screen} via DeepLink handler...")
            stack.push(target_screen, params)
        else:
            print(f"  {Colors.RED}[X] No matching prefix or route pattern. Ignored or fallback to NotFoundScreen.{Colors.RESET}")

    render_navigation_tree(stack)

    print(f"{Colors.BOLD}4. Simulasi Reset Action (Auth Logout / State Rehydration):{Colors.RESET}")
    print(f"[ACTION] dispatch(CommonActions.reset({{ routes: [{{ name: 'LoginScreen' }}] }}))")
    stack.reset([("LoginScreen", {"sessionExpired": True})])
    render_navigation_tree(stack)

    print(f"{Colors.GREEN}{Colors.BOLD}Simulasi Navigasi dan Deep Linking selesai dengan sukses!{Colors.RESET}\n")

if __name__ == "__main__":
    run_simulation()
