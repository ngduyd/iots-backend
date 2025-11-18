import grpc
import data_service_pb2, data_service_pb2_grpc
import config
from google.protobuf.timestamp_pb2 import Timestamp
from datetime import datetime

class DataSyncService(data_service_pb2_grpc.DataSyncServiceServicer):
    def __init__(self):
        target = f'{config.RECIVER_HOST}:{config.RECIVER_PORT}'
        if config.RECIVER_HOST in ['localhost', '127.0.0.1']:
            self.channel = grpc.insecure_channel(target)
        else:
            # self.channel = grpc.secure_channel(target, grpc.ssl_channel_credentials())
            self.channel = grpc.insecure_channel(target)
        self.stub = data_service_pb2_grpc.DataSyncServiceStub(self.channel)
        self.device_api_key = config.DEVICE_API_KEY

    def UploadSensor(self, name: str, vbat: float, status: str) -> bool:
        """Synchronous gRPC call for uploading sensor info."""
        metadata = (('x-device-id', self.device_api_key),)

        try:
            print(f"Uploading sensor: {name}, vbat: {vbat}, status: {status}")
            request = data_service_pb2.Sensor(
                name=name,
                vbat=vbat,
                status=status
            )
            response = self.stub.UploadSensor(request, metadata=metadata, timeout=5)
            print(f"UploadSensor response: {response}")
            return response.success
        except Exception as e:
            print(f"Error in UploadSensor: {e}")
            return False

    def UploadSingleRow(self, sensor_id: int, type: str, value: float, create_at: datetime) -> bool:
        """Synchronous gRPC call for uploading sensor data."""
        metadata = (('x-device-id', self.device_api_key),)

        ts = Timestamp()
        ts.FromDatetime(create_at)

        try:
            request = data_service_pb2.DataRow(
                sensor_id=sensor_id,
                type=type,
                value=value,
                create_at=ts
            )
            response = self.stub.UploadSingleRow(request, metadata=metadata, timeout=5)
            return response.success
        except Exception as e:
            print(f"Error in UploadSingleRow: {e}")
            return False
