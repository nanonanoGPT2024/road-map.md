// scripts/inspect-ast.ts
import * as ts from 'typescript';

const sourceCode = `
export interface UserPayload {
  id: string;
  roles: string[];
}

export function processUser(payload: UserPayload): boolean {
  return payload.roles.length > 0;
}

const activeUser: UserPayload = {
  id: "usr_1029",
  roles: ["admin", "editor"]
};

export const isAuthorized = processUser(activeUser);
`;

const dummyFileName = 'virtualModule.ts';

// 1. Buat Virtual SourceFile
const sourceFile = ts.createSourceFile(
  dummyFileName,
  sourceCode,
  ts.ScriptTarget.ES2022,
  /* setParentNodes */ true,
  ts.ScriptKind.TS
);

// 2. Buat Compiler Host Virtual untuk isolasi eksekusi tanpa menyentuh I/O Disk
const compilerOptions: ts.CompilerOptions = {
  target: ts.ScriptTarget.ES2022,
  module: ts.ModuleKind.NodeNext,
  strict: true,
  declaration: true
};

const customCompilerHost: ts.CompilerHost = {
  getSourceFile: (fileName) => (fileName === dummyFileName ? sourceFile : undefined),
  getDefaultLibFileName: () => 'lib.d.ts',
  writeFile: () => {},
  getCurrentDirectory: () => '/',
  getDirectories: () => [],
  getCanonicalFileName: (fileName) => fileName,
  useCaseSensitiveFileNames: () => true,
  getNewLine: () => '\n',
  fileExists: (fileName) => fileName === dummyFileName,
  readFile: (fileName) => (fileName === dummyFileName ? sourceCode : undefined),
};

// 3. Inisialisasi TS Program & Akses TypeChecker
const program = ts.createProgram([dummyFileName], compilerOptions, customCompilerHost);
const checker = program.getTypeChecker();

// 4. Traversal AST Menggunakan ts.forEachChild
function traverseAst(node: ts.Node, depth: number = 0) {
  const indent = '  '.repeat(depth);
  const syntaxKindName = ts.SyntaxKind[node.kind];

  // Identifikasi deklarasi spesifik
  if (ts.isFunctionDeclaration(node) && node.name) {
    const symbol = checker.getSymbolAtLocation(node.name);
    if (symbol) {
      const type = checker.getTypeOfSymbolAtLocation(symbol, node);
      const signatureString = checker.typeToString(type);
      console.log(`${indent}>> [FUNCTION] ${symbol.getName()} : ${signatureString}`);
    }
  } else if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
    const symbol = checker.getSymbolAtLocation(node.name);
    if (symbol) {
      const type = checker.getTypeOfSymbolAtLocation(symbol, node);
      const typeString = checker.typeToString(type);
      console.log(`${indent}>> [VARIABLE] ${symbol.getName()} Evaluated Type: ${typeString}`);
    }
  } else {
    console.log(`${indent}(${syntaxKindName})`);
  }

  ts.forEachChild(node, (child) => traverseAst(child, depth + 1));
}

console.log('--- AST TRAVERSAL & TYPE CHECKING OUTPUT ---');
traverseAst(sourceFile);
