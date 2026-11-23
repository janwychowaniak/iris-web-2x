module_name = "IrisFacadeRenderer"
module_description = ("Renders enrichment data stored in ioc_enrichment (written by an "
                      "automation engine via REST API) into per-service IOC attribute tabs. "
                      "Pure renderer: no external calls, no credentials.")
interface_version = "1.2.0"
module_version = "0.2.0"
pipeline_support = False
pipeline_info = {}

module_configuration = [
    {
        "param_name": "frr_on_update_hook_enabled",
        "param_human_name": "Render on IOC update",
        "param_description": "Render facade reports into IOC tabs whenever an IOC is updated",
        "default": True,
        "mandatory": True,
        "type": "bool",
        "section": "Triggers",
    },
    {
        "param_name": "frr_manual_hook_enabled",
        "param_human_name": "Manual trigger",
        "param_description": "Adds 'Render facade reports' to the IOC right-click menu",
        "default": True,
        "mandatory": True,
        "type": "bool",
        "section": "Triggers",
    },
]

# Names that a database registering 0.1.1 already holds; they never change.
update_hook = "on_postload_ioc_update"
manual_hook = "on_manual_trigger_ioc"
manual_hook_name = "Render facade reports"
field_name = "HTML report"
field_type = "html"
