# milkwashr

Deterministic sentence-chunk assembly for the [milkwash](https://github.com/twardoch/milkwash)
text-laundering pipeline. Rust core, importable from Python as `milkwashr`.

Sentence *segmentation* happens upstream in Python (`sentencex`, which has
explicit Arabic and Polish support). This crate does *chunk assembly*: group
2–8 sentences per chunk with a seeded RNG, then apply
[`text-splitter`](https://crates.io/crates/text-splitter) as a size guard so an
over-long chunk cannot overflow a small model's context window.

The RNG is seeded per source text, so every model in a sweep replays the
identical chunk plan — without that, no two models see the same input and the
outputs are not comparable.

## Python

```python
import milkwashr

milkwashr.ping()                                   # "milkwashr-ok"
milkwashr.plan_chunk_spans(42, seed=1234)          # [(0, 5), (5, 9), ...]
milkwashr.assemble_chunks(sentences, seed=1234)    # list[str]
milkwashr.split_by_size(text, max_chars=6000)      # list[str]
```

## Rust

```rust
let spans = milkwashr::plan_chunk_spans(42, 1234, 2, 8);
```

## License

Apache-2.0
