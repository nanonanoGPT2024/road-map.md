// Memastikan compatibility metadata
(Symbol as any).metadata ??= Symbol("Symbol.metadata");

// Tipe HTTP Method
type HttpMethod = "GET" | "POST" | "DELETE" | "PUT";

// Definisi Struktur Metadata Routing
interface RouteMetadata {
  method: HttpMethod;
  path: string;
  handlerName: string | symbol;
  roles?: string[];
}

// Global metadata symbols
const ROUTES_KEY = Symbol("routes");

// 1. ROUTE DECORATOR FACTORY
function Route(method: HttpMethod, path: string) {
  return function <This, Args extends any[], Return>(
    target: (this: This, ...args: Args) => Return,
    context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => Return>
  ) {
    const meta = context.metadata;
    if (!meta[ROUTES_KEY]) {
      meta[ROUTES_KEY] = [] as RouteMetadata[];
    }

    const routes = meta[ROUTES_KEY] as RouteMetadata[];
    routes.push({
      method,
      path,
      handlerName: context.name,
    });

    return target;
  };
}

// 2. AUTHORIZATION DECORATOR FACTORY
function Roles(requiredRoles: string[]) {
  return function <This, Args extends any[], Return>(
    target: (this: This, ...args: Args) => Return,
    context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => Return>
  ) {
    const meta = context.metadata;
    const routes = (meta[ROUTES_KEY] ?? []) as RouteMetadata[];
    const currentRoute = routes.find((r) => r.handlerName === context.name);

    if (currentRoute) {
      currentRoute.roles = requiredRoles;
    }

    // Wrap target with authorization interceptor
    return function (this: This, ...args: Args): Return {
      const user = (this as any).currentUser;
      if (!user) {
        throw new Error(`401 Unauthorized: Session not found.`);
      }

      const hasRole = requiredRoles.some((role) => user.roles.includes(role));
      if (!hasRole) {
        throw new Error(`403 Forbidden: Insufficient permissions for ${String(context.name)}`);
      }

      return target.apply(this, args);
    };
  };
}

// 3. BASE CONTROLLER
abstract class BaseController {
  currentUser: { id: string; roles: string[] } | null = null;

  public setUserContext(user: { id: string; roles: string[] } | null) {
    this.currentUser = user;
  }
}

// 4. BUSINESS CONTROLLER IMPLEMENTATION
class UserController extends BaseController {
  private users = [
    { id: "1", name: "Alice", role: "ADMIN" },
    { id: "2", name: "Bob", role: "USER" },
  ];

  @Route("GET", "/users")
  @Roles(["ADMIN"])
  public getAllUsers() {
    return this.users;
  }

  @Route("GET", "/me")
  @Roles(["ADMIN", "USER"])
  public getCurrentUser() {
    return this.currentUser;
  }
}

// 5. APPLICATION ROUTE DISPATCHER ENGINE
class MiniDispatcher {
  public static dispatch(
    controllerInstance: BaseController,
    method: HttpMethod,
    path: string
  ): any {
    const prototype = Object.getPrototypeOf(controllerInstance);
    const metadata = (controllerInstance.constructor as any)[Symbol.metadata];

    if (!metadata || !metadata[ROUTES_KEY]) {
      throw new Error(`No route metadata configured.`);
    }

    const routes = metadata[ROUTES_KEY] as RouteMetadata[];
    const route = routes.find((r) => r.method === method && r.path === path);

    if (!route) {
      return { status: 404, body: "Not Found" };
    }

    try {
      const handler = (controllerInstance as any)[route.handlerName];
      const result = handler.call(controllerInstance);
      return { status: 200, body: result };
    } catch (err: any) {
      if (err.message.startsWith("401")) return { status: 401, body: err.message };
      if (err.message.startsWith("403")) return { status: 403, body: err.message };
      return { status: 500, body: "Internal Server Error" };
    }
  }
}

// 6. VERIFIKASI RUNTIME (TEST SUITE EXECUTION)
console.log("=== EXECUTION TEST SUITE ===");
const controller = new UserController();

// Request 1: Unauthorized Access
console.log("Req 1 (No Auth):", MiniDispatcher.dispatch(controller, "GET", "/users"));

// Request 2: Insufficient Permission (Logged as USER, hits ADMIN endpoint)
controller.setUserContext({ id: "user-2", roles: ["USER"] });
console.log("Req 2 (Forbidden):", MiniDispatcher.dispatch(controller, "GET", "/users"));

// Request 3: Success Permission for ADMIN
controller.setUserContext({ id: "admin-1", roles: ["ADMIN"] });
console.log("Req 3 (Success Admin):", MiniDispatcher.dispatch(controller, "GET", "/users"));

// Request 4: Access User Endpoint
console.log("Req 4 (Success User):", MiniDispatcher.dispatch(controller, "GET", "/me"));
