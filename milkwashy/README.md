# milkwashy

The Python half of [milkwash](https://github.com/twardoch/milkwash): does an LLM
paraphrase pass wash a statistical text watermark out of a document?

`milkwashy` takes long source texts, splits them into 2–8 sentence chunks,
rewrites every chunk through a randomly assigned rephrase prompt, and repeats
the run against every model a local OpenAI-compatible server can serve. Chunk
assembly is done by the Rust extension [`milkwashr`](https://pypi.org/project/milkwashr/).

```bash
uv pip install milkwashy

milkwashy init_config       # TOML config in the platformdirs location
milkwashy gen_indata        # write the four seed texts to 01-indata/
milkwashy models            # list models (LM Studio via `lms`, others via /v1/models)
milkwashy plan              # show the chunk + prompt plan, no inference
milkwashy run --limit 5     # sweep the 5 smallest models
```

Full documentation: <https://github.com/twardoch/milkwash>

## License

Apache-2.0
