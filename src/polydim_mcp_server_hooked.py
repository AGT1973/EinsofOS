"""
POLYDIM-EINSOF | Ariel Garcia Traba (Independent Research)
POLYDIM V26505 VECTOR-CONTROL-PLANE MCP SERVER
==============================================
Connects Antigravity MCP Control Plane directly to the 8 real distilled POLYDIM
open-weights models (`qwen2_5_PMTP_version_1_0/2_0`, `deepseekx_x_PMTP_version_1_0/2_0`,
`llamax_x_PMTP_version_1_0/2_0`, `gemmax_x_PMTP_version_1_0/2_0`) via `PolydimVectorSwarmHub`.

STRICT GHOST PROTOCOL (Rules 22, 23, 24):
- No latent vector is ever serialized into JSON/Markdown over MCP stdio.
- All tensor handovers occur in native IEEE-754 FP64 shared memory (`PmtpShmBus` + mmap slabs).
- Only 64-byte `SLAB_ID` pointers and physical silicon metrics are returned on the control plane.
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any

if "E:/PMTP" not in sys.path and r"E:\PMTP" not in sys.path:
    sys.path.insert(0, r"E:\PMTP")

from pmtp_polydim_vector_swarm import PolydimVectorSwarmHub, CANONICAL_MODELS

MCP_DIR = Path(r"C:\Users\eluithi\.gemini\antigravity\mcp\mcp-polydim")
LOG_PATH = MCP_DIR / "polydim_mcp.log"
logging.basicConfig(level=logging.INFO, filename=str(LOG_PATH))

_HUB: PolydimVectorSwarmHub = None


def get_hub() -> PolydimVectorSwarmHub:
    global _HUB
    if _HUB is None:
        _HUB = PolydimVectorSwarmHub()
    return _HUB


def handle_polydim_inference(args: Dict[str, Any]) -> Dict[str, Any]:
    hub = get_hub()
    family = args.get("model_family", "qwen2_5_PMTP_version_1_0")
    slab_in = args.get("slab_id_in", args.get("slab_id", "0x1001"))
    slab_out = args.get("slab_id_out", "0x1002")
    prompt = args.get("prompt_boundary", "POLYDIM_BOUNDARY_SEED")
    recur_steps = int(args.get("recur_steps", 4))
    return hub.execute_vector_agent(
        model_name=family,
        slab_id_in=slab_in,
        slab_id_out=slab_out,
        prompt_boundary=prompt,
        recur_steps=recur_steps
    )


def handle_polydim_vector_swarm(args: Dict[str, Any]) -> Dict[str, Any]:
    hub = get_hub()
    chain = args.get("agent_chain", CANONICAL_MODELS)
    init_slab = args.get("initial_slab_id", "0x2000")
    prompt = args.get("prompt_boundary", "POLYDIM_SWARM_SEED")
    recur_steps = int(args.get("recur_steps", 4))
    return hub.execute_multi_agent_vector_chain(
        agent_chain=chain,
        initial_slab_id=init_slab,
        prompt_boundary=prompt,
        recur_steps=recur_steps
    )


def handle_pmtp_compute_tensor(args: Dict[str, Any]) -> Dict[str, Any]:
    hub = get_hub()
    slab_in = args.get("slab_id_in", "0x3001")
    slab_out = args.get("slab_id_out", "0x3002")
    model_name = args.get("model_name", "deepseekx_x_PMTP_version_1_0")
    return hub.execute_vector_agent(
        model_name=model_name,
        slab_id_in=slab_in,
        slab_id_out=slab_out,
        recur_steps=4
    )


def handle_hacedor_vector_bounce(args: Dict[str, Any]) -> Dict[str, Any]:
    slab_in = args.get("slab_id_in", "0xSLAB_MCP_IN_001")
    slab_out = args.get("slab_id_out", "0xSLAB_ALADIN_OUT_002")
    dim = int(args.get("dimension", 2048))
    
    if "E:/POLYDIM_EINSOF/EINSOF_OS/src" not in sys.path:
        sys.path.insert(0, "E:/POLYDIM_EINSOF/EINSOF_OS/src")
    from einsof_hacedor_runtime import HacedorSiliconWorker
    worker = HacedorSiliconWorker(dimension=dim)
    res = worker.execute_bounce_cycle(slab_id_in=slab_in, slab_id_out=slab_out)
    return {
        "agent": "hacedor",
        "exit_code": res["exit_code"],
        "slab_id_in": res["slab_id_in"],
        "slab_id_out": res["slab_id_out"],
        "dimension": res["dimension"],
        "bytes_transferred": res["byte_len"],
        "tokens_burned": 0,
        "latency_ms": round(res["elapsed_ms"], 2),
        "aladin_proc_ms": round(res["aladin_proc_ms"], 2),
        "orthonormal_error": res["ortho_err"],
        "status": "SUCCESS"
    }


def get_tools_list():
    with open(MCP_DIR / "polydim_inference.json", "r", encoding="utf-8") as f:
        schema_inf = json.load(f)
    with open(MCP_DIR / "polydim_vector_swarm.json", "r", encoding="utf-8") as f:
        schema_swarm = json.load(f)
    with open(MCP_DIR / "pmtp_compute_tensor.json", "r", encoding="utf-8") as f:
        schema_comp = json.load(f)
    
    tools = [
        {
            "name": "polydim_inference",
            "description": "Ejecuta un agente de modelo abierto mejorado con POLYDIM (Qwen 2.5, DeepSeek R1, LLaMA 3, Gemma 2 v1.0/v2.0) directamente sobre memoria compartida vectorial PMTP (SLAB_ID).",
            "inputSchema": schema_inf.get("parameters", schema_inf)
        },
        {
            "name": "polydim_vector_swarm",
            "description": "Orquesta una cadena multi-agente de los 8 modelos POLYDIM transfiriendo tensores FP64 en memoria compartida PmtpShmBus (SLAB_ID_k -> SLAB_ID_{k+1}, 0 tokens 1D).",
            "inputSchema": schema_swarm.get("parameters", schema_swarm)
        },
        {
            "name": "pmtp_compute_tensor",
            "description": "Transporte y proyección isométrica de tensores en memoria compartida PMTP con verificación Neumaier FP64.",
            "inputSchema": schema_comp.get("parameters", schema_comp)
        }
    ]

    hacedor_json = MCP_DIR / "hacedor_vector_bounce.json"
    if hacedor_json.exists():
        with open(hacedor_json, "r", encoding="utf-8") as f:
            schema_hacedor = json.load(f)
        tools.append({
            "name": "hacedor_vector_bounce",
            "description": "Puerta de rebote en silicio para el agente 'hacedor': opera tensores continuos en RAM y ALADIN con CERO tokens 1D quemados.",
            "inputSchema": schema_hacedor.get("parameters", schema_hacedor)
        })

    return tools


def dispatch_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "polydim_inference":
        return handle_polydim_inference(arguments)
    elif name == "polydim_vector_swarm":
        return handle_polydim_vector_swarm(arguments)
    elif name == "pmtp_compute_tensor":
        return handle_pmtp_compute_tensor(arguments)
    elif name == "hacedor_vector_bounce":
        return handle_hacedor_vector_bounce(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line.strip())
            method = req.get("method")
            msg_id = req.get("id")
            params = req.get("params", {})

            if method == "initialize":
                res = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "mcp-polydim-vector-swarm", "version": "26505.0"}
                }
                print(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": res}), flush=True)
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                print(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": get_tools_list()}}), flush=True)
            elif method == "tools/call":
                t_name = params.get("name")
                t_args = params.get("arguments", {})
                out = dispatch_tool(t_name, t_args)
                content = [{"type": "text", "text": json.dumps(out)}]
                print(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {"content": content, "isError": False}}), flush=True)
            elif method in ("polydim_inference", "polydim_vector_swarm", "pmtp_compute_tensor"):
                out = dispatch_tool(method, params)
                print(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {"content": json.dumps(out)}}), flush=True)
            else:
                if msg_id is not None:
                    print(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {}}), flush=True)
        except Exception as e:
            logging.error(f"Error processing MCP request: {e}")
            if "msg_id" in locals() and msg_id is not None:
                print(json.dumps({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32000, "message": str(e)}}), flush=True)


if __name__ == "__main__":
    main()
