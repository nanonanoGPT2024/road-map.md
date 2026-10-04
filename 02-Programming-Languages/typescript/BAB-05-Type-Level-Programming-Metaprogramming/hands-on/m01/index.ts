// ============================================================================
// 1. URL ROUTE PARAMETER EXTRACTOR
// ============================================================================

type ExtractRouteParams<Path extends string> = 
  Path extends `${string}:${infer Param}/${infer Rest}`
    ? { [K in Param | keyof ExtractRouteParams<`/${Rest}`>]: string }
    : Path extends `${string}:${infer Param}`
      ? { [K in Param]: string }
      : Record<string, never>;

// Verifikasi Ekstraksi Parameter
type UserPostRoute = '/tenants/:tenantId/users/:userId/posts/:postId';
type ExtractedParams = ExtractRouteParams<UserPostRoute>;
// Resulting Type:
// type ExtractedParams = {
//   tenantId: string;
//   userId: string;
//   postId: string;
// }

// ============================================================================
// 2. TYPE-SAFE DEEP OBJECT PATH (GETTER/SETTER)
// ============================================================================

type Primitive = string | number | boolean | bigint | symbol | undefined | null;

/**
 * Membentuk union seluruh path valid dalam dot-notation string
 */
export type DeepNestedPaths<T, Depth extends unknown[] = []> = 
  // Batasi kedalaman traversal hingga 5 level untuk mencegah compiler hang
  Depth['length'] extends 5
    ? never
    : T extends Primitive
      ? never
      : T extends readonly (infer Element)[]
        ? `${number}` | `${number}.${DeepNestedPaths<Element, [...Depth, unknown]>}`
        : {
            [K in keyof T & string]: 
              | K 
              | `${K}.${DeepNestedPaths<T[K], [...Depth, unknown]>}`
          }[keyof T & string];

/**
 * Mengambil tipe dari nilai pada dot-notation path
 */
export type DeepNestedValue<T, Path extends string> = 
  Path extends `${infer Key}.${infer Rest}`
    ? Key extends keyof T
      ? DeepNestedValue<T[Key], Rest>
      : Key extends `${number}`
        ? T extends readonly (infer Element)[]
          ? DeepNestedValue<Element, Rest>
          : never
        : never
    : Path extends keyof T
      ? T[Path]
      : Path extends `${number}`
        ? T extends readonly (infer Element)[]
          ? Element
          : never
        : never;

// ============================================================================
// 3. RUNTIME IMPLEMENTATION (ZERO RUNTIME COST PARITY)
// ============================================================================

export function get<
  TData extends Record<string, any>, 
  TPath extends DeepNestedPaths<TData>
>(
  data: TData, 
  path: TPath
): DeepNestedValue<TData, TPath> {
  const segments = (path as string).split('.');
  let current: any = data;

  for (const segment of segments) {
    if (current === null || current === undefined) {
      return undefined as DeepNestedValue<TData, TPath>;
    }
    current = current[segment];
  }

  return current as DeepNestedValue<TData, TPath>;
}

// ============================================================================
// 4. TESTING HARNESS
// ============================================================================

interface SystemConfig {
  database: {
    replicas: {
      url: string;
      port: number;
    }[];
    timeoutMs: number;
  };
  features: {
    experimentalEngine: boolean;
  };
}

const config: SystemConfig = {
  database: {
    replicas: [
      { url: 'db1.internal', port: 5432 },
      { url: 'db2.internal', port: 5433 }
    ],
    timeoutMs: 5000
  },
  features: {
    experimentalEngine: true
  }
};

// Valid calls: Kompilator menginferensikan tipe balik secara absolut tepat!
const dbTimeout = get(config, 'database.timeoutMs');           // Tipe: number
const primaryUrl = get(config, 'database.replicas.0.url');       // Tipe: string
const isEnabled = get(config, 'features.experimentalEngine');    // Tipe: boolean

// @ts-expect-error Kompilator menggagalkan jika path salah!
const invalidField = get(config, 'database.replikas');

// @ts-expect-error Indeks salah secara struktural
const invalidSubField = get(config, 'database.replicas.invalidKey');
