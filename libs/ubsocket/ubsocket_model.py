"""UBSocket Model classes migrated from legency/testcase/ubscomm/ubsocket/lib/model/UBSocket_Model.py"""

from libs.ubsocket import k8s_api as k8s


class Container_Dev_Info:
    """Container device information."""
    
    def __init__(self, avg_lat, p99_lat, qps, server_cpu, client_cpu):
        self.avg_lat = avg_lat

    def get_info(self):
        """Get container-device mapping on machine."""
        pass


class Client_result:
    """Client test result container."""
    
    def __init__(self, avg_lat, p90_lat, p99_lat, p999_lat, qps, server_cpu, client_cpu, throughput):
        self.avg_lat = avg_lat
        self.p90_lat = p90_lat
        self.p99_lat = p99_lat
        self.p999_lat = p999_lat
        self.qps = qps
        self.server_cpu = server_cpu
        self.client_cpu = client_cpu
        self.throughput = throughput

    @staticmethod
    def get_info_from_str(info_str):
        """Parse info string to extract value."""
        info = info_str.strip().split(":")[1]
        if "%" in info:
            value = info.split("%")[0].strip()
        elif "MB/s" in info:
            value = info.split("MB/s")[0].strip()
        else:
            value = info
        return float(value)

    @classmethod
    def collect_info(cls, datas: list):
        """Collect info from data list."""
        avg_lat = 0
        p90_lat = 0
        p99_lat = 0
        p999_lat = 0
        qps = 0
        server_cpu = 0
        client_cpu = 0
        throughput = 0
        for item in datas:
            if "Avg-Latency" in item:
                avg_lat = cls.get_info_from_str(item)
            if "90th" in item:
                p90_lat = cls.get_info_from_str(item)
            if "99th" in item:
                p99_lat = cls.get_info_from_str(item)
            if "99.9th" in item:
                p999_lat = cls.get_info_from_str(item)
            if "QPS" in item:
                qps = cls.get_info_from_str(item)
            if "Server CPU-utilization" in item:
                server_cpu = cls.get_info_from_str(item)
            if "Client CPU-utilization" in item:
                client_cpu = cls.get_info_from_str(item)
            if "Throughput" in item:
                throughput = cls.get_info_from_str(item)
        return cls(avg_lat, p90_lat, p99_lat, p999_lat, qps, server_cpu, client_cpu, throughput)