"""TurboCommBaseCase - Root base class for TurboComm (HCOM/HSHMEM/NetMind) test cases.

Migrated from: legency/testcase/ubscomm/hcom/lib/basecase/TurboCommBaseCase.py
Provides common server/client execution methods for TurboComm tests.

Legacy inheritance: TurboCommBaseCase(Case) 
Pytest adaptation: TurboCommBaseCase(TestCase)
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from libs.core.base import TestCase
from libs.hcom.node_run import node_run, node_ssh, create_ssh, close_ssh, send_cmd_list
from libs.hcom.result_verify import verify, verify_not, check_latency_output, update_if_not_fail

logger = logging.getLogger(__name__)


class TurboCommBaseCase(TestCase):
    """Root base class for TurboComm (HCOM/HSHMEM/NetMind) test cases."""
    
    def get_nodes(self) -> List[Any]:
        """Get list of test nodes from resource.
        
        Legacy method: self.get_nodes()
        Returns nodes from resource.hosts mapping.
        
        Returns:
            List of node objects from resource.hosts
        """
        if self.resource and "hosts" in self.resource:
            hosts = self.resource["hosts"]
            return [hosts[str(i + 1)] for i in range(len(hosts))]
        return self.nodes
    
    def base_run(
        self,
        nodes: List[Any],
        executor: ThreadPoolExecutor,
        run_dir: str,
        cmd_s: List[str],
        cmd_c: List[str],
        inputs_s: Optional[List[str]] = None,
        inputs_c: Optional[List[str]] = None,
        waitstr_s: str = "@#>",
        waitstr_c: str = "@#>",
        expects_s: Optional[List[str]] = None,
        expects_c: Optional[List[str]] = None,
        not_expects_s: Optional[List[str]] = None,
        not_expects_c: Optional[List[str]] = None,
        sleep_time: int = 10,
        check_time: int = 1
    ) -> Dict[str, str]:
        """Run HCOM/HSHMEM server/client test with input/output verification.
        
        Legacy method: self.base_run(nodes, executor, run_dir, cmd_s, cmd_c, ...)
        
        Args:
            nodes: Test server nodes list [server, client]
            executor: ThreadPoolExecutor for parallel execution
            run_dir: Directory to run test commands
            cmd_s: Server command list
            cmd_c: Client command list
            inputs_s: Server input commands after startup
            inputs_c: Client input commands after startup
            waitstr_s: Server wait string to indicate completion
            waitstr_c: Client wait string to indicate completion
            expects_s: Expected strings in server output
            expects_c: Expected strings in client output
            not_expects_s: Strings that should NOT appear in server output
            not_expects_c: Strings that should NOT appear in client output
            sleep_time: Sleep time between server and client start
            check_time: Number of times to check expected output
            
        Returns:
            Dictionary with "server" and "client" result status ("pass"/"fail")
        """
        server, client = nodes[0], nodes[1]
        
        # Start server thread
        self.logStep(f"Creating server on {server.localIP}")
        future_s = executor.submit(
            node_run, node=server, command=cmd_s, 
            input_str=inputs_s, directory=run_dir, waitstr=waitstr_s
        )
        time.sleep(sleep_time)
        
        # Start client thread
        self.logStep(f"Creating client on {client.localIP}")
        future_c = executor.submit(
            node_run, node=client, command=cmd_c,
            input_str=inputs_c, directory=run_dir, waitstr=waitstr_c
        )
        time.sleep(20)
        
        res_s, res_c = future_s.result(), future_c.result()
        
        # Log results
        self.logInfo(f"res_server: {res_s}")
        self.logInfo(f"res_client: {res_c}")
        
        self.logStep("Verifying test results")
        result_dataset = {}
        
        # Verify server results
        if res_s.get('rc') == 0:
            if verify(res_s.get("stdout"), expects_s):
                result_dataset["server"] = "pass"
            else:
                result_dataset["server"] = "fail"
        else:
            result_dataset["server"] = "fail"
        
        # Verify client results
        if res_c.get('rc') == 0:
            if verify(res_c.get("stdout"), expects_c):
                result_dataset["client"] = "pass"
            else:
                result_dataset["client"] = "fail"
        else:
            result_dataset["client"] = "fail"
        
        # Verify NOT expects
        if not_expects_s is not None:
            if verify_not(res_s.get("stdout"), not_expects_s):
                result_dataset["server"] = "pass"
            else:
                result_dataset["server"] = "fail"
        
        if not_expects_c is not None:
            msg = res_c.get("stdout").split("Verbs Destroy endpoint")[0]
            if verify_not(msg, not_expects_c):
                result_dataset["client"] = "pass"
            else:
                result_dataset["client"] = "fail"
        
        self.logStep("Test completed")
        return result_dataset
    
    def base_run_nohup(
        self,
        nodes: List[Any],
        executor: ThreadPoolExecutor,
        run_dir: str,
        cmd_s: List[str],
        cmd_c: List[str],
        cmd_check_s: Optional[List[str]] = None,
        cmd_check_c: Optional[List[str]] = None,
        expects_s: Optional[List[str]] = None,
        expects_c: Optional[List[str]] = None,
        wait_time: int = 60
    ) -> None:
        """Run server/client in background with nohup for large output tests.
        
        Legacy method: self.base_run_nohup(nodes, executor, run_dir, cmd_s, cmd_c, ...)
        
        Args:
            nodes: Test server nodes list [server, client]
            executor: ThreadPoolExecutor for parallel execution
            run_dir: Directory to run test commands
            cmd_s: Server command list (nohup format)
            cmd_c: Client command list (nohup format)
            cmd_check_s: Server check command (e.g., cat nohup.out)
            cmd_check_c: Client check command
            expects_s: Expected strings in server nohup output
            expects_c: Expected strings in client nohup output
            wait_time: Wait time for nohup result check
        """
        server, client = nodes[0], nodes[1]
        
        # Clean up old nohup.out
        self.logStep("Deleting nohup.out logs")
        executor.submit(node_run, node=server, command=["rm -f nohup.out"], directory=run_dir)
        executor.submit(node_run, node=client, command=["rm -f nohup.out"], directory=run_dir)
        time.sleep(5)
        
        # Start server
        self.logStep(f"Creating server on {server.localIP}")
        executor.submit(node_run, node=server, command=cmd_s, directory=run_dir, timeout=180)
        time.sleep(5)
        
        # Start client
        self.logStep(f"Creating client on {client.localIP}")
        executor.submit(node_run, node=client, command=cmd_c, directory=run_dir, timeout=180)
        time.sleep(wait_time)
        
        # Verify nohup results
        self.logStep("Verifying nohup test results")
        
        if cmd_check_s is not None:
            future_s = executor.submit(node_run, node=server, command=cmd_check_s, directory=run_dir)
            res_s = future_s.result()
            self.logInfo(f"res_server: {res_s}")
            self.assertEqual(res_s.get('rc'), 0)
            if expects_s is not None:
                self.assertTrue(verify(res_s.get("stdout"), expects_s))
        
        if cmd_check_c is not None:
            future_c = executor.submit(node_run, node=client, command=cmd_check_c, directory=run_dir)
            res_c = future_c.result()
            self.logInfo(f"res_client: {res_c}")
            self.assertEqual(res_c.get('rc'), 0)
            if expects_c is not None:
                self.assertTrue(verify(res_c.get("stdout"), expects_c))
        
        self.logStep("Test completed")
    
    def base_run_ssh(
        self,
        server: Any,
        client: Any,
        executor: ThreadPoolExecutor,
        cmd_s: List[str],
        cmd_c: List[str],
        inputs_s: Optional[List[str]] = None,
        inputs_c: Optional[List[str]] = None,
        expects_s: Optional[List[str]] = None,
        expects_c: Optional[List[str]] = None,
        expects_lat: str = None,
        not_expects_s: Optional[List[str]] = None,
        not_expects_c: Optional[List[str]] = None,
        wait_time: int = 20,
        sleep_time: int = 10
    ) -> Dict[str, str]:
        """Run server/client via SSH channel for interactive tests.
        
        Legacy method: self.base_run_ssh(server, client, executor, cmd_s, cmd_c, ...)
        
        Args:
            server: Server node object
            client: Client node object
            executor: ThreadPoolExecutor
            cmd_s: Server command list
            cmd_c: Client command list
            inputs_s: Server input commands
            inputs_c: Client input commands
            expects_s: Expected server output strings
            expects_c: Expected client output strings
            expects_lat: Expected client output strings
            not_expects_s: Unexpected server output strings
            not_expects_c: Unexpected client output strings
            wait_time: Server wait time
            sleep_time: Client sleep time
            
        Returns:
            Dictionary with "server" and "client" result status
        """
        ch_s, ssh_s = create_ssh(server)
        ch_c, ssh_c = create_ssh(client)
        
        # Start server
        self.logStep(f"Starting server process on {server.localIP}")
        self.logDebug(f"server command: {cmd_s}")
        executor.submit(send_cmd_list, ch_s, cmd_s, time1=wait_time, inputs=inputs_s, time2=5)
        time.sleep(5)
        
        # Start client
        self.logStep(f"Starting client process on {client.localIP}")
        self.logDebug(f"client command: {cmd_c}")
        executor.submit(send_cmd_list, ch_c, cmd_c, time1=5, inputs=inputs_c, time2=sleep_time)
        
        time.sleep(wait_time + sleep_time)
        
        # Verify results
        self.logStep("Verifying test results")
        res_s = ch_s.recv(65535000000).decode("utf-8")
        self.logDebug(f"res_server: {res_s}")
        
        res_c = ch_c.recv(65535000000).decode("utf-8")
        self.logDebug(f"res_client: {res_c}")
        
        result_dataset = {}
        if verify(res_s, expects_s):
            update_if_not_fail(result_dataset, "server", "pass")
        else:
            update_if_not_fail(result_dataset, "server", "fail")
        
        if verify(res_c, expects_c):
            update_if_not_fail(result_dataset, "client", "pass")
        else:
            update_if_not_fail(result_dataset, "client", "fail")

        if expects_lat is not None:
            if check_latency_output(res_c, expects_lat):
                update_if_not_fail(result_dataset, "client", "pass")
            else:
                update_if_not_fail(result_dataset, "client", "fail")
        
        if not_expects_s is not None:
            if verify_not(res_s, not_expects_s):
                update_if_not_fail(result_dataset, "server", "pass")
            else:
                update_if_not_fail(result_dataset, "server", "fail")

        if not_expects_c is not None:
            if verify_not(res_c, not_expects_c):
                update_if_not_fail(result_dataset, "client", "pass")
            else:
                update_if_not_fail(result_dataset, "client", "fail")
        
        close_ssh([ch_s, ch_c])
        self.logStep("Test completed")
        return result_dataset
    
    def base_kill(
        self,
        nodes: List[Any],
        executor: ThreadPoolExecutor,
        run_dir: str,
        cmd_s: str,
        cmd_c: str
    ) -> None:
        """Kill server/client processes on nodes.
        
        Legacy method: self.base_kill(nodes, executor, run_dir, cmd_s, cmd_c)
        
        Args:
            nodes: [server, client] node list
            executor: ThreadPoolExecutor
            run_dir: Directory where processes run
            cmd_s: Server process name to kill
            cmd_c: Client process name to kill
        """
        server, client = nodes[0], nodes[1]
        
        self.logStep(f"Killing server on {server.localIP}")
        kill_s_cmd = "ps -ef|grep '" + cmd_s.strip() + "' | grep -v grep |awk '{print $2}'|xargs -i kill -9 {}"
        executor.submit(node_run, node=server, command=[kill_s_cmd], directory=run_dir)
        
        self.logStep(f"Killing client on {client.localIP}")
        kill_c_cmd = "ps -ef|grep '" + cmd_c.strip() + "' | grep -v grep |awk '{print $2}'|xargs -i kill -9 {}"
        executor.submit(node_run, node=client, command=[kill_c_cmd], directory=run_dir)
    
    def client_list_run(
        self,
        nodes: List[Any],
        executor: ThreadPoolExecutor,
        direction: str,
        cmd_c: List[str],
        cmd_s: Optional[List[str]] = None,
        inputs: Optional[List[str]] = None,
        waitstr: str = "@#>",
        expects_c: Optional[List[str]] = None,
        client_num: int = 1,
        timeout: int = 900
    ) -> None:
        """Run multiple concurrent client processes.
        
        Legacy method: self.client_list_run(nodes, executor, direction, cmd_c, ...)
        
        Args:
            nodes: [server, client] node list
            executor: ThreadPoolExecutor
            direction: Run directory
            cmd_c: Client command list
            cmd_s: Optional server command list
            inputs: Client input commands
            waitstr: Client wait string
            expects_c: Expected client output strings
            client_num: Number of concurrent clients
            timeout: Timeout for each client
        """
        server, client = nodes[0], nodes[1]
        
        if cmd_s is not None:
            # Start server
            self.logStep(f"Creating server on {server.localIP}")
            node = node_ssh(server)
            executor.submit(node_run, node=node, command=cmd_s, directory=direction, timeout=timeout)
            time.sleep(10)
        
        # Create multiple client connections
        self.logStep(f"Creating {client_num} clients on {client.localIP}")
        future_c = []
        node_c = []
        res_c = []
        
        # Create new connections (time-consuming)
        for idx in range(client_num):
            node_c.append(node_ssh(client))
        
        # Run clients
        for idx in range(client_num):
            future_c.append(
                executor.submit(
                    node_run, node=node_c[idx], command=cmd_c,
                    directory=direction, input_str=inputs,
                    waitstr=waitstr, timeout=timeout
                )
            )
        
        if expects_c is not None:
            self.logStep("Verifying test results")
            for idx in range(client_num):
                res_c.append(future_c[idx].result())
                self.assertEqual(res_c[idx].get('rc'), 0)
                self.assertTrue(verify(res_c[idx].get("stdout"), expects_c))
                self.assertTrue(verify_not(res_c[idx].get("stdout"), ["ERROR"]))