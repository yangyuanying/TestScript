#encoding:utf-8

import paramiko
import time
import threading

class SSHConnection(object):

    #初始化
    def __init__(self, host, port, username, password):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._transport = None
        self._client = None
        #self._sftp = None
        self._connect()

    #连接、建立ssh通道		
    def _connect(self):
        transport = paramiko.Transport(self._host,self._port)
        transport.connect(username=self._username,password=self._password)
        self._transport = transport
	
	#执行命令
    def exec_command(self,command):
        if self._client is None:
            self._client = paramiko.SSHClient()
            self._client._transport = self._transport
        stdin, stdout, stderr = self._client.exec_command(command)
        data = stdout.read()
        if len(data) > 0:
            print (data.strip()) #打印正确结果
            return data
        err = stderr.read()
        if len(err) > 0:
            print (err.strip()) #输出错误结果
            return err

    #上传
    def upload(self,localpath,remotepath):
        if self._sftp is None:
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
        self._sftp.put(localpath,remotepath)

    #下载
    def download(self,remotepath,localpath):
        if self._sftp is None:
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
        self._sftp.get(remotepath,localpath)

    #关闭ssh通道
    def close(self):
        if self._transport:
            self._transport.close()
        if self._client:
            self._client.close()

#重启设备
def reboot(conn):

    conn.exec_command('ubus call mnt reboot')
    time.sleep (10)
    conn.close()

#检查重启			
def check_reboot(conn):

    data = conn.exec_command('ls -la /tmp/test_flag')
    data = data.decode('utf8')
    if ("No such file or directory" in data):
        print ("********** 设备升级重启成功 **********")
        return 1
    else:
        print ("********** 设备升级重启失败 **********")
        return 0

def check_ssh_connect(ip,username,password):

    conn = SSHConnection(ip,22,username,password)
    result = SSHConnection._connect(conn)
    return result
	
if __name__ == "__main__":
	
    check_times = input("请输入要测试的次数：")
    check_times = int(check_times)
    ip = input("请输入测试设备的IP地址：")
    username = input("请输入测试设备的用户名：")
    password = input("请输入测试设备的密码：")
    test_times = 1
	
    while test_times <= check_times:
        
        conn = SSHConnection(ip,22,username,password)
        print ("********** 第%d次重启测试开始 **********" %test_times)
        conn.exec_command('rm -f /tmp/test_flag')
        conn.exec_command('touch /tmp/test_flag')
        t = threading.Thread(target=reboot,args=(conn,))
        t.setDaemon(True)
        t.start()
        t.join(100)
        time.sleep(100)
        print("********** 结束等待重启的进程 **********")
        conn = SSHConnection(ip,22,username,password)
        time.sleep (5)
        data = conn.exec_command('ubus call upgrade get_status')
        data = data.decode('utf8')
        str_1 = "upgrade_local_version"
        if (str_1 in data):
            print ("********** SSH连接建立成功 **********")
        else:
            print ("********** SSH连接建立失败，重新尝试建立连接 **********")
            allow_retry_times = 100
            retry_times = 0
            while retry_times < allow_retry_times:
                conn = SSHConnection(ip,22,username,password)
                data = conn.exec_command('ubus call upgrade get_status')
                data = data.decode('utf8')
                str_1 = "upgrade_local_version"
                if (str_1 in data):
                    print ("********** SSH连接建立成功 **********")
                    break
                else:
                    retry_times = retry_times + 1
                    time.sleep(10)
            if (retry_times == allow_retry_times):
                print ("********** 重启测试，第%d次失败。 **********" %test_times)
                print ("********** 系统重启后,SSH连接建立超时 **********" )
                test_times = test_times + 1
                continue			
        if (check_reboot(conn) == 1):
            print ("********** 第%d次重启测试结束，重启成功 **********" %test_times)
            test_times = test_times + 1
            time.sleep(60)
        else:
            print ("********** 第%d次重启测试结束，重启失败 **********" %test_times)
            test_times = test_times + 1
            time.sleep(60)
