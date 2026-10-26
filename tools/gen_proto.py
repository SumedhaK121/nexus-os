"""NEXUS-OS Protobuf & gRPC Stub Generator.
Compiles proto/nexus.proto into communication/generated/ stubs using grpc_tools.protoc.
Fixes standard relative import paths for package portability.
"""

import os
import sys

try:
    import grpc_tools.protoc
    HAS_GRPC_TOOLS = True
except ImportError:
    HAS_GRPC_TOOLS = False


def generate():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proto_dir = os.path.join(root, "proto")
    proto_file = os.path.join(proto_dir, "nexus.proto")
    out_dir = os.path.join(root, "communication", "generated")
    os.makedirs(out_dir, exist_ok=True)

    init_file = os.path.join(out_dir, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w", encoding="utf-8") as f:
            f.write("# NEXUS-OS Generated gRPC stubs\n")

    if not HAS_GRPC_TOOLS:
        print("[gen_proto] Warning: grpc_tools is not installed. Skipping stub generation.")
        return False

    print(f"[gen_proto] Compiling {proto_file} -> {out_dir} ...")
    ret = grpc_tools.protoc.main([
        "protoc",
        f"-I{proto_dir}",
        f"--python_out={out_dir}",
        f"--grpc_python_out={out_dir}",
        proto_file,
    ])

    if ret != 0:
        print(f"[gen_proto] Error: protoc compilation failed with code {ret}")
        return False

    # Fix gRPC Python relative import issue:
    # grpc_tools generates: import nexus_pb2 as nexus__pb2
    # In package context, we replace with: from communication.generated import nexus_pb2 as nexus__pb2
    grpc_stub_file = os.path.join(out_dir, "nexus_pb2_grpc.py")
    if os.path.exists(grpc_stub_file):
        with open(grpc_stub_file, "r", encoding="utf-8") as f:
            content = f.read()
        target = "import nexus_pb2 as nexus__pb2"
        replacement = "from communication.generated import nexus_pb2 as nexus__pb2"
        if target in content:
            content = content.replace(target, replacement)
            with open(grpc_stub_file, "w", encoding="utf-8") as f:
                f.write(content)
            print("[gen_proto] Patched nexus_pb2_grpc.py import path")

    print("[gen_proto] Generated gRPC stubs successfully!")
    return True


if __name__ == "__main__":
    success = generate()
    sys.exit(0 if success else 1)
