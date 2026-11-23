#!/usr/bin/env python3
#
#  IrisFacadeRenderer: renders ioc_enrichment into IOC attribute tabs.
#  Data flow: an automation engine writes reputation facade answers (ENVELOPE.md v1) into
#  ioc_enrichment (JSONB) through the REST API --hook--> this module --> one `html` tab per
#  service key, through add_tab_attribute_field. Pure renderer: no external calls, no
#  credentials. The rendering is in render.py; this file is the IRIS side.

import traceback

import iris_interface.IrisInterfaceStatus as InterfaceStatus
from iris_interface.IrisModuleInterface import IrisModuleInterface, IrisModuleTypes

from app import db
from app.datamgmt.manage.manage_attribute_db import add_tab_attribute_field

import iris_facade_renderer_module.IrisFacadeRendererConfig as interface_conf
from iris_facade_renderer_module import render


class IrisFacadeRendererInterface(IrisModuleInterface):
    name = "IrisFacadeRendererInterface"
    _module_name = interface_conf.module_name
    _module_description = interface_conf.module_description
    _interface_version = interface_conf.interface_version
    _module_version = interface_conf.module_version
    _pipeline_support = interface_conf.pipeline_support
    _pipeline_info = interface_conf.pipeline_info
    _module_configuration = interface_conf.module_configuration
    _module_type = IrisModuleTypes.module_processor

    def register_hooks(self, module_id: int):
        self.module_id = module_id
        conf = self.module_dict_conf
        if conf.get("frr_on_update_hook_enabled"):
            status = self.register_to_hook(module_id, iris_hook_name=interface_conf.update_hook)
            self.log.info("%s: %s" % (interface_conf.update_hook,
                                      "registered" if not status.is_failure() else status.get_message()))
        else:
            self.deregister_from_hook(module_id=module_id, iris_hook_name=interface_conf.update_hook)

        if conf.get("frr_manual_hook_enabled"):
            status = self.register_to_hook(module_id, iris_hook_name=interface_conf.manual_hook,
                                           manual_hook_name=interface_conf.manual_hook_name)
            self.log.info("%s: %s" % (interface_conf.manual_hook,
                                      "registered" if not status.is_failure() else status.get_message()))
        else:
            self.deregister_from_hook(module_id=module_id, iris_hook_name=interface_conf.manual_hook)

    def hooks_handler(self, hook_name: str, hook_ui_name: str, data):
        self.log.info("Received %s" % hook_name)
        if hook_name not in (interface_conf.update_hook, interface_conf.manual_hook):
            self.log.critical("Received unsupported hook %s" % hook_name)
            return InterfaceStatus.I2Error(data=data, logs=list(self.message_queue))
        try:
            all_written = render.render_iocs(data, self._write_tab, self.log)
        except Exception:  # render_iocs handles every value and every write; this is a bug
            self.log.error(traceback.format_exc())
            all_written = False
        status = InterfaceStatus.I2Success if all_written else InterfaceStatus.I2Error
        return status(data=data, logs=list(self.message_queue))

    @staticmethod
    def _write_tab(ioc, tab, body):
        """Write one tab. After a failed write the session is rolled back, so that the next
        tab and IOC can still be written: add_tab_attribute_field commits once per tab."""
        try:
            written = add_tab_attribute_field(ioc, tab_name=tab, field_name=interface_conf.field_name,
                                              field_type=interface_conf.field_type, field_value=body)
        except Exception:
            db.session.rollback()
            raise
        if not written:
            db.session.rollback()
        return written
