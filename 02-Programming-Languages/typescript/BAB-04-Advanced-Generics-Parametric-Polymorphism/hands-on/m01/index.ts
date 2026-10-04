// ==========================================
// CQRS Core Contracts
// ==========================================

export interface IMessage<TKind extends string = string> {
  readonly kind: TKind;
}

// Marker generic interface dengan inferensi output type
export interface IRequest<TResponse> extends IMessage {
  readonly __responseMarker?: TResponse; // Phantom property untuk type inferencing
}

export interface IRequestHandler<
  in TReq extends IRequest<TRes>,
  out TRes
> {
  handle(request: TReq): Promise<TRes>;
}

// Pipeline Middleware contract
export type NextMiddleware<TRes> = () => Promise<TRes>;

export interface IPipelineBehavior {
  handle<TReq extends IRequest<TRes>, TRes>(
    request: TReq,
    next: NextMiddleware<TRes>
  ): Promise<TRes>;
}

// ==========================================
// Mediator Implementation
// ==========================================

export class Mediator {
  private readonly handlers = new Map<string, IRequestHandler<any, any>>();
  private readonly middlewares: IPipelineBehavior[] = [];

  public registerHandler<
    TRes,
    TReq extends IRequest<TRes>
  >(
    kind: TReq["kind"],
    handler: IRequestHandler<TReq, TRes>
  ): void {
    if (this.handlers.has(kind)) {
      throw new Error(`Handler already registered for: ${kind}`);
    }
    this.handlers.set(kind, handler);
  }

  public use(middleware: IPipelineBehavior): void {
    this.middlewares.push(middleware);
  }

  public async send<TRes>(request: IRequest<TRes>): Promise<TRes> {
    const handler = this.handlers.get(request.kind);
    if (!handler) {
      throw new Error(`No handler registered for message kind: ${request.kind}`);
    }

    // Eksekusi middleware chain menggunakan higher-order functions
    const executionChain = this.middlewares.reduceRight<NextMiddleware<TRes>>(
      (next, middleware) => {
        return () => middleware.handle(request, next);
      },
      () => handler.handle(request)
    );

    return executionChain();
  }
}

// ==========================================
// Domain Concrete Implementation
// ==========================================

// Domain Entities & DTOs
export interface UserDTO {
  id: string;
  email: string;
  role: "ADMIN" | "MEMBER";
}

// Command Definition: Mengikat request ke output type 'UserDTO'
export class CreateUserCommand implements IRequest<UserDTO> {
  public readonly kind = "CreateUserCommand";
  public readonly __responseMarker?: UserDTO;

  constructor(
    public readonly email: string,
    public readonly role: "ADMIN" | "MEMBER"
  ) {}
}

// Handler Definition: Terikat erat dengan CreateUserCommand & UserDTO
export class CreateUserHandler
  implements IRequestHandler<CreateUserCommand, UserDTO>
{
  public async handle(command: CreateUserCommand): Promise<UserDTO> {
    // Simulasi persistensi ke Database
    return {
      id: "usr_" + Math.random().toString(36).substring(2, 9),
      email: command.email,
      role: command.role,
    };
  }
}

// Global Validation Middleware
export class LoggingMiddleware implements IPipelineBehavior {
  public async handle<TReq extends IRequest<TRes>, TRes>(
    request: TReq,
    next: NextMiddleware<TRes>
  ): Promise<TRes> {
    const startTime = performance.now();
    console.log(`[CQRS-LOG] Executing: ${request.kind}`);

    try {
      const result = await next();
      const duration = (performance.now() - startTime).toFixed(2);
      console.log(`[CQRS-LOG] Completed: ${request.kind} in ${duration}ms`);
      return result;
    } catch (error) {
      console.error(`[CQRS-LOG] Failed: ${request.kind}`, error);
      throw error;
    }
  }
}

// ==========================================
// Verification & Execution Runner
// ==========================================

async function bootstrap() {
  const mediator = new Mediator();

  mediator.use(new LoggingMiddleware());

  const createUserHandler = new CreateUserHandler();
  mediator.registerHandler("CreateUserCommand", createUserHandler);

  // INFERENSI OTOMATIS:
  // result terinferensi sebagai UserDTO secara deterministik!
  const command = new CreateUserCommand("tech-lead@enterprise.org", "ADMIN");
  const result = await mediator.send(command);

  console.log(`User created with ID: ${result.id}, Role: ${result.role}`);
}

void bootstrap();
