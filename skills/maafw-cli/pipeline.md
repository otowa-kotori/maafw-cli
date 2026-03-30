# Pipeline — multi-node automation

Pipeline lets you define multi-step automation flows in JSON. Nodes are linked via `next` and executed sequentially with built-in recognition and action.

## Protocol reference

- 中文: <https://maafw.com/docs/3.1-PipelineProtocol>
- English: <https://maafw.com/en/docs/3.1-PipelineProtocol>

## Node structure

Each node is a JSON object with a recognition step and an action step:

```json
{
  "NodeName": {
    "recognition": "TemplateMatch",
    "template": ["button.png"],
    "action": "Click",
    "next": ["NextNode"]
  }
}
```

### Recognition types

`DirectHit` · `TemplateMatch` · `FeatureMatch` · `ColorMatch` · `OCR` · `NeuralNetworkClassify` · `NeuralNetworkDetect` · `Custom`

### Action types

`DoNothing` · `Click` · `LongPress` · `Swipe` · `Key` · `InputText` · `StartApp` · `StopApp` · `StopTask` · `Custom`

Full parameter lists for each type: [node-params.md](node-params.md)

## maafw-cli pipeline commands

```bash
# Load pipeline JSON
maafw-cli --on game pipeline load ./pipeline/

# List loaded nodes
maafw-cli --on game pipeline list

# Show a node definition
maafw-cli --on game pipeline show GameLoop

# Validate pipeline (no execution)
maafw-cli --on game pipeline validate ./pipeline/

# Run pipeline from an entry node
maafw-cli --on game pipeline run ./pipeline/ ClickPlay

# Run with node overrides
maafw-cli --on game pipeline run ./pipeline/ ClickPlay --override '{"NodeA": {"timeout": 5000}}'

# JSON output with per-node details
maafw-cli --on game --json pipeline run ./pipeline/ ClickPlay
```
