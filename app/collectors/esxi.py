"""VMware ESXi / vCenter collector using pyVmomi (vSphere API)."""
from __future__ import annotations

import asyncio
import ssl
import threading
from typing import Any

from ..config import ESXiConfig
from .base import Collector, CollectorError


class ESXiCollector(Collector):
    name = "esxi"
    label = "ESXi"

    def __init__(self, cfg: ESXiConfig) -> None:
        self.cfg = cfg
        self._si = None
        self._lock = threading.Lock()

    # -- connection -------------------------------------------------------
    def _connect(self):
        from pyVim.connect import SmartConnect  # lazy import

        if self._si is not None:
            try:
                self._si.CurrentTime()
                return self._si
            except Exception:
                self._si = None
        ctx = None
        if not self.cfg.verify_ssl:
            ctx = ssl._create_unverified_context()  # noqa: S323 - homelab self-signed certs
        self._si = SmartConnect(
            host=self.cfg.host,
            user=self.cfg.user,
            pwd=self.cfg.password,
            port=self.cfg.port,
            sslContext=ctx,
        )
        return self._si

    def _view(self, si, vimtype):
        content = si.RetrieveContent()
        view = content.viewManager.CreateContainerView(content.rootFolder, [vimtype], True)
        try:
            return list(view.view)
        finally:
            view.Destroy()

    # -- collect ----------------------------------------------------------
    def _collect_sync(self) -> dict[str, Any]:
        from pyVmomi import vim

        with self._lock:
            si = self._connect()
            hosts = []
            for h in self._view(si, vim.HostSystem):
                hw = h.summary.hardware
                qs = h.summary.quickStats
                cpu_total = (hw.cpuMhz or 0) * (hw.numCpuCores or 0)
                mem_total = hw.memorySize or 0
                hosts.append(
                    {
                        "name": h.name,
                        "version": h.summary.config.product.fullName if h.summary.config else "",
                        "model": f"{hw.vendor} {hw.model}".strip(),
                        "cpu_cores": hw.numCpuCores,
                        "cpu_pct": round(100 * (qs.overallCpuUsage or 0) / cpu_total, 1) if cpu_total else 0,
                        "mem_pct": round(100 * (qs.overallMemoryUsage or 0) * 1024 * 1024 / mem_total, 1) if mem_total else 0,
                        "mem_total": mem_total,
                        "uptime_s": qs.uptime or 0,
                        "state": str(h.runtime.connectionState),
                    }
                )

            datastores = []
            for ds in self._view(si, vim.Datastore):
                s = ds.summary
                datastores.append({"name": s.name, "capacity": s.capacity, "free": s.freeSpace, "type": s.type})

            vms = []
            for vm in self._view(si, vim.VirtualMachine):
                s = vm.summary
                if s.config is None or s.config.template:
                    continue
                macs = []
                try:
                    for dev in vm.config.hardware.device:
                        if isinstance(dev, vim.vm.device.VirtualEthernetCard):
                            macs.append(dev.macAddress.lower())
                except Exception:
                    pass
                snaps = []
                if vm.snapshot:
                    stack = list(vm.snapshot.rootSnapshotList)
                    while stack:
                        sn = stack.pop()
                        snaps.append({"name": sn.name, "created": sn.createTime.timestamp()})
                        stack.extend(sn.childSnapshotList)
                qs = s.quickStats
                max_cpu = s.runtime.maxCpuUsage or 0
                vms.append(
                    {
                        "id": vm._moId,
                        "name": s.config.name,
                        "state": {"poweredOn": "on", "poweredOff": "off", "suspended": "suspended"}.get(
                            str(s.runtime.powerState), str(s.runtime.powerState)
                        ),
                        "os": s.config.guestFullName,
                        "vcpu": s.config.numCpu,
                        "mem_mb": s.config.memorySizeMB,
                        "cpu_pct": round(100 * (qs.overallCpuUsage or 0) / max_cpu, 1) if max_cpu else 0,
                        "mem_pct": round(100 * (qs.guestMemoryUsage or 0) / s.config.memorySizeMB, 1)
                        if s.config.memorySizeMB
                        else 0,
                        "ip": s.guest.ipAddress if s.guest else None,
                        "tools": str(s.guest.toolsRunningStatus) if s.guest else None,
                        "macs": macs,
                        "snapshots": snaps,
                    }
                )
            vms.sort(key=lambda v: (v["state"] != "on", v["name"].lower()))
            return {"hosts": hosts, "datastores": datastores, "vms": vms}

    async def collect(self) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(self._collect_sync)
        except Exception as exc:  # reset session on any failure
            self._si = None
            raise CollectorError(str(exc)) from exc

    # -- actions ----------------------------------------------------------
    def _action_sync(self, kind: str, target: str) -> str:
        from pyVmomi import vim

        with self._lock:
            si = self._connect()
            vm = next((v for v in self._view(si, vim.VirtualMachine) if v._moId == target), None)
            if vm is None:
                raise CollectorError(f"VM {target} not found")
            if kind == "power_on":
                vm.PowerOnVM_Task()
            elif kind == "shutdown":
                vm.ShutdownGuest()
            elif kind == "power_off":
                vm.PowerOffVM_Task()
            elif kind == "reboot":
                vm.RebootGuest()
            else:
                raise CollectorError(f"Unknown action {kind}")
            return f"{kind} sent to {vm.name}"

    async def action(self, kind: str, target: str, **kwargs: Any) -> str:
        return await asyncio.to_thread(self._action_sync, kind, target)

    async def close(self) -> None:
        if self._si is not None:
            from pyVim.connect import Disconnect

            try:
                Disconnect(self._si)
            except Exception:
                pass
