protoc -I=. --python_out=. ./autotest.proto
mv autotest_pb2.py autotest_pb.py
sed s/google/googlepb/g autotest_pb.py > autotest_pb2.py
rm autotest_pb.py
