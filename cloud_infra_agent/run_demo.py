# import json
# from pathlib import Path

# from cloud_infra_agent.cloud_eval_agent import CloudEvalAgent, Inputs


# def load_inputs(path: str) -> Inputs:
#     """Load inputs from a JSON file into the Inputs dataclass."""
#     data = json.loads(Path(path).read_text())
#     return Inputs(
#         inventory_adapters=data["inventory_adapters"],
#         resources=data["resources"],
#         compute_instances=data["compute_instances"],
#         k8s_rows=data["k8s_rows"],
#         ts_metrics=data["ts_metrics"],
#         scale_events=data["scale_events"],
#         db_metrics=data["db_metrics"],
#         lb_metrics=data["lb_metrics"],
#         block_volumes=data["block_volumes"],
#         snapshots=data["snapshots"],
#         objects=data["objects"],
#         lifecycle_rules=data["lifecycle_rules"],
#         iac_index=data["iac_index"],
#         policy_findings=data["policy_findings"],
#         incidents=data["incidents"],
#         slo_breaches=data["slo_breaches"],
#         cost_rows=data["cost_rows"],
#         commit_inventory=data["commit_inventory"],
#         usage=data["usage"],
#         rightsizing=data["rightsizing"],
#         egress_costs=data["egress_costs"],
#         net_metrics=data["net_metrics"],
#         network_policies=data["network_policies"],
#         storage_acls=data["storage_acls"],
#         security_resources_crypto_tls=(
#             data["security_resources_crypto_tls"]
#         ),
#         iam_dump=data["iam_dump"],
#         vuln_findings=data["vuln_findings"],
#         patch_status=data["patch_status"],
#         cspm_findings=data["cspm_findings"],
#         kms_keys=data["kms_keys"],
#         secrets=data["secrets"],
#         gpu_metrics=data["gpu_metrics"],
#         gpu_cost_rows=data["gpu_cost_rows"],
#         iac_runs=data["iac_runs"],
#     )


# def main() -> None:
#     """Run the evaluation agent and write results to a report file."""
#     inputs = load_inputs("cloud_infra_agent/sample_data.json")
#     agent = CloudEvalAgent()
#     results = agent.run_all(inputs)

#     out_path = Path("cloud_infra_agent/report.json")
#     out_path.write_text(json.dumps(results, indent=2))
#     print("Wrote", out_path)


# if __name__ == "__main__":
#     main()
