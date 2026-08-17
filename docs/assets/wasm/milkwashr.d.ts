/* tslint:disable */
/* eslint-disable */

/**
 * Tells you that the module is loaded and can run.
 */
export function ping(): string;

/**
 * Makes a complete plan from sentences that are already separated.
 *
 * `sentences` must hold one sentence in each item. The function returns a
 * `Plan` object. If a chunk is longer than `max_chars` characters, the size
 * guard cuts it, and then the chunk count is more than the span count.
 */
export function plan(sentences: string[], min_sent: number, max_sent: number, max_chars: number): any;

/**
 * Gives the four rephrase prompts, in index order.
 */
export function prompts(): string[];

/**
 * Cuts a text by size only. Use this when the sentences are not available.
 */
export function split_by_size(text: string, max_chars: number): string[];

/**
 * Gives the seed of a text, as a decimal string.
 */
export function text_seed(text: string): string;

/**
 * Gives the version of the crate that built this module.
 */
export function version(): string;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly ping: () => [number, number];
    readonly plan: (a: number, b: number, c: number, d: number, e: number) => [number, number, number];
    readonly prompts: () => [number, number];
    readonly split_by_size: (a: number, b: number, c: number) => [number, number];
    readonly text_seed: (a: number, b: number) => [number, number];
    readonly version: () => [number, number];
    readonly __wbindgen_malloc: (a: number, b: number) => number;
    readonly __wbindgen_realloc: (a: number, b: number, c: number, d: number) => number;
    readonly __wbindgen_exn_store: (a: number) => void;
    readonly __externref_table_alloc: () => number;
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __wbindgen_free: (a: number, b: number, c: number) => void;
    readonly __externref_table_dealloc: (a: number) => void;
    readonly __externref_drop_slice: (a: number, b: number) => void;
    readonly __wbindgen_start: () => void;
}

export type SyncInitInput = BufferSource | WebAssembly.Module;

/**
 * Instantiates the given `module`, which can either be bytes or
 * a precompiled `WebAssembly.Module`.
 *
 * @param {{ module: SyncInitInput }} module - Passing `SyncInitInput` directly is deprecated.
 *
 * @returns {InitOutput}
 */
export function initSync(module: { module: SyncInitInput } | SyncInitInput): InitOutput;

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
export default function __wbg_init (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;
