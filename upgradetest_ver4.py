#encoding:utf-8

import paramiko
import time
from urllib import request
from urllib import parse
import json
import os
import threading

# 机器人 Webhook地址
ROBOT_WEBHOOK = ""

#磁盘路径

def build_text_msg(msg):
    params = dict()
    params["msgtype"] = "text"
    params["text"] = dict()
    params["text"]["content"] = msg
    params["at"] = dict()
    params["at"]["atMobiles"] = '[""]'
    params["at"]["isAtAll"] = False
    print (params)
    post_data = json.dumps(params)
	
    return post_data

def send_msg(post_data):
    global ROBOT_WEBHOOK
    url_path = ROBOT_WEBHOOK
	
    req = request.Request(url_path)
    req.add_header('Content-Type', 'application/json')
	
    try:
        with request.urlopen(req, data=post_data.encode('utf-8')) as f:
            print ('Status:', f.status, f.reason)
            for k,v in f.getheaders():
                print ('%s: %s' % (k,v))
            resp_data = f.read().decode('utf-8')
        return resp_data
    except Exception as e:
        print ("Error:", e)
        resp_data = '{"errcode":0}'
        return resp_data
		
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
        try:
            transport = paramiko.Transport(self._host,self._port)
            transport.connect(username=self._username,password=self._password)
            self._transport = transport
            return 1
        except paramiko.ssh_exception.SSHException as e:
            print ('ssh连接发生错误：',e)
            return 0
	
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

class MyThread(threading.Thread):

    def __init__(self,func,args=()):
        super(MyThread,self).__init__()
        self.func = func
        self.args = args

    def run(self):
        self.result = self.func(*self.args)

    def get_result(self):
        return self.result
		
#重启设备
def reboot(conn):

    conn.exec_command('ubus call mnt reboot')
    time.sleep(20)

#检查是否重启成功			
def check_reboot():

    conn = SSHConnection(ip,22,username,password)
    data = conn.exec_command('ls -la /tmp/before_reboot')
    data = data.decode('utf8')
    if ("No such file or directory" in data):
        print ("********** 设备重启成功 **********")
        return 1
    else:
        print ("********** 设备重启失败 **********")
        return 0

#回退后/升级后，检查system包版本是否正确
def request_system_version(conn):

    result = conn.exec_command('ubus call upgrade get_status')
    time.sleep(15)
    return result

def check_system_ver(conn):

    allow_retry_times = 120
    retry_times = 0
    while retry_times < allow_retry_times:
        t = MyThread(func=request_system_version,args=(conn,))
        t.setDaemon(True)
        t.start()
        t.join(20)
        print ("********** 结束查询system包版本的进程 **********")
        try:
            a = t.get_result()
            print (a)
            if (a is None):
                retry_times = retry_times + 1
                continue
            else:
                version = a.decode('utf8')
                print ("version: %s" %version)
                version_1 = "1.0.427"
                if (version_1 in version):
                    print ("********** 系统版本为 1.0.427 **********")
                    return 1
                else:
                    print ("********** 系统版本不为 1.0.427 **********")
                    return 0
        except AttributeError as e:
            print ("********** 查询system包版本子线程超时 **********")
            retry_times = retry_times + 1
            time.sleep(10)
            continue
			
#回退后/升级后，检查system包挂载结构：/instaboot分区是否挂载
def request_mount_structure(conn):

    result = conn.exec_command('df -h |grep instaboot |cut -d "\n" -f 2')
    time.sleep(15)
    return result
	
def check_mount_structure(conn):

    allow_retry_times = 120
    retry_times = 0
    while retry_times < allow_retry_times:
        t = MyThread(func=request_mount_structure,args=(conn,))
        t.setDaemon(True)
        t.start()
        t.join(20)
        print ("********** 结束查询/instaboot分区挂载情况的进程 **********")
        try:
            a = t.get_result()
            print (a)
            if (a is None):
                print ("********** /instaboot分区没有挂载 **********")
                return 0
            else:
                data = a.decode('utf8')
                print (data)
                if ("/dev/instaboot" in data and "/instaboot" in data and "/high" not in data): 
                    print ("********** /instaboot分区正常挂载 **********")
                    return 1
        except AttributeError as e:
            print ("********** 查询system包版本子线程超时 **********")
            retry_times = retry_times + 1
            time.sleep(10)
            continue
		
#回退后/升级后，检查系统关键目录
def check_key_catalogues(conn):

    conn.exec_command('cp -f /media/sda1/change_flags_script/check_key_cata.sh /tmp')
    conn.exec_command('chmod +x /tmp/check_key_cata.sh')
    conn.exec_command('sh /tmp/check_key_cata.sh')
    data = conn.exec_command('cat /tmp/2')
    data_1 = 'yes\n'.encode()
    if (data == data_1):
        print ("********** /instaboot/otc_base目录存在 **********")
        conn.exec_command('rm -f /tmp/2')
        return 1
    else:
        print ("********** /instaboot/otc_base目录不存在 **********")
        conn.exec_command('rm -f /tmp/2')
        return 0

def check_key_catalogues_1(conn):
    
    data = conn.exec_command('cat /tmp/.otc_info/base_part_conf.txt')
    data = data.decode('utf8')
    if ("No such file or directory" in data):
        print ("********** /instaboot/otc_base目录不存在 **********")
        return 1
    else:
        print ('********** /instaboot/otc_base目录存在 **********')
        return 0	

#回退后/升级后，检查根文件系统的类型
def request_rootfs(conn):

    result = conn.exec_command('df -h|grep -w "/"|cut -d " " -f 1')
    time.sleep(15)
    return result

def check_rootfs(conn):

    allow_retry_times = 120
    retry_times = 0
    while retry_times < allow_retry_times:
        t = MyThread(func=request_rootfs,args=(conn,))
        t.setDaemon(True)
        t.start()
        t.join(20)
        print ("********** 结束查询根文件系统类型的进程 **********")
        try:
            a = t.get_result()
            print (a)
            data_1 = 'overlay\n'.encode()
            if (a == data_1):
                print ("********** 根文件系统类型为overlay **********")
                return 1
            else:
                print ("********** 根文件系统类型不为overlay **********")
                return 0
        except AttributeError as e:
            print ("********** 查询根文件系统类型子线程超时 **********")
            retry_times = retry_times + 1
            time.sleep(10)
            continue
		
#改变标志位，切换启动分区为/dev/xxx,使得系统版本回退为V1.0.427
def change_flags(conn):
    conn.exec_command('rm -f /tmp/1')
    conn.exec_command('cp -f /media/sda1/change_flags_script/change_flags.sh /tmp')
    conn.exec_command('chmod +x /tmp/change_flags.sh')
    conn.exec_command('sh /tmp/change_flags.sh')
    data = conn.exec_command('cat /tmp/1')
    data_1 = 'yes\n'.encode()
    if (data == data_1):
        print ("********** 标志位切换成功 **********")
        conn.exec_command('rm -f /tmp/1')
        return 1
    else:
        print ("********** 标志位切换失败 **********")
        conn.exec_command('rm -f /tmp/1')
        return 0

#删除/misc/app_master文件
def delete_misc_app_master(conn):

    conn.exec_command('rm -f /misc/app_master')
    data = conn.exec_command('ls -la /misc/app_master')
    data = data.decode('utf8')
    if ("No such file or directory" in data):
        print ("********** /misc/app_master文件已经删除 **********")
        return 1
    else:
        print ('********** /misc/app_master文件未删除 **********')
        return 0

#删除/misc/base_master文件
def delete_misc_base_master(conn):

    conn.exec_command('rm -f /misc/base_master')
    data = conn.exec_command('ls -la /misc/base_master')
    data = data.decode('utf8')
    if ("No such file or directory" in data):
        print ("********** /misc/base_master文件已经删除 **********")
        return 1
    else:
        print ('********** /misc/base_master文件未删除 **********')
        return 0

#设备升级
def upgrade(conn):

    conn.exec_command ('ubus call upgrade install_local \'{"package":"/media/sda1/onecloud-system_V2.0.1_arm.ipk","force":false}\'')
	
def upgrade_1(conn):

    b = conn.exec_command ('ubus call upgrade probe_server')
    conn.exec_command ('ubus call upgrade start')
    time.sleep(10)
    conn.close()

#检查upgrade版本
def request_upgrade_version(conn):

    result = conn.exec_command('ubus call upgrade get_status')
    time.sleep(15)
    return result

def check_upgrade_ver(conn):

    allow_retry_times = 120
    retry_times = 0
    while retry_times < allow_retry_times:
        t = MyThread(func=request_upgrade_version,args=(conn,))
        t.setDaemon(True)
        t.start()
        t.join(20)
        print ("********** 结束查询upgrade模块版本的进程 **********")
        try:
            a = t.get_result()
            print (a)
            version = a.decode('utf8')
            version_1 = "1.2.3"
            if (version_1 in version):
                print ("********** upgrade版本为 1.2.3 **********")
                return 1
            else:
                print ("********** upgrade版本不为 1.2.3 **********")
                return 0
        except AttributeError as e:
            print ("********** 查询upgrade模块版本子线程超时 **********")
            retry_times = retry_times + 1
            time.sleep(10)
            continue
		
#检查SSH是否连接成功
def check_ssh_connect(ip,username,password):

    conn = SSHConnection(ip,22,username,password)
    result = SSHConnection._connect(conn)
    return result
			
#检查profile文件大小
def request_profie_size(conn):

    result = conn.exec_command('ls -la /etc/profile|cut -d " " -f 21')
    time.sleep(15)
    return result  
	
def check_profile_size(conn):
    
    allow_retry_times = 120
    retry_times = 0
    while retry_times < allow_retry_times:
        t = MyThread(func=request_profie_size,args=(conn,))
        t.setDaemon(True)
        t.start()
        t.join(20)
        print ("********** 结束查询profile文件大小的进程 **********")
        try:
            a = t.get_result()
            print (a)
            size = a.decode('utf8')
            size = int(size)
            if (size >= 1536 and size <= 2600):
                print ("********** profile文件大小正常 **********")
                return 1
            else:
                print ("********** profile文件大小异常 **********")
                return 0
        except AttributeError as e:
            print ("********** 查询profile文件大小子线程超时 **********")
            retry_times = retry_times + 1
            time.sleep(10)
            continue

#检查/etc/passwd、/etc/shadow、/etc/group文件
def request_etc_file_content_1(conn):

    result = conn.exec_command('cat /etc/passwd|grep "root"') 
    time.sleep(15)	
    return result

def check_etc_file_content_1(conn):

    allow_retry_times = 120
    retry_times = 0
    while retry_times < allow_retry_times:
        t = MyThread(func=request_etc_file_content_1,args=(conn,))
        t.setDaemon(True)
        t.start()
        t.join(20)
        print ("********** 结束查询/etc/passwd的进程 **********")
        try:
            a = t.get_result()
            print (a)
            if (a is None):
                print ("********** 系统配置文件检查错误 **********")
                return 0
            else:
                print ("********** 系统配置文件检查成功 **********")
                return 1
        except AttributeError as e:
            print ("********** 查询查询/etc/passwd子进程超时 **********")
            retry_times = retry_times + 1
            time.sleep(10)
            continue

def request_etc_file_content_2(conn):

    result = conn.exec_command('cat /etc/shadow|grep "root"')
    time.sleep(15)	
    return result

def check_etc_file_content_2(conn):
	
    allow_retry_times = 120
    retry_times = 0
    while retry_times < allow_retry_times:
        t = MyThread(func=request_etc_file_content_2,args=(conn,))
        t.setDaemon(True)
        t.start()
        t.join(20)
        print ("********** 结束查询/etc/shadow的进程 **********")
        try:
            a = t.get_result()
            print (a)
            if (a is None):
                print ("********** 系统配置文件检查错误 **********")
                return 0
            else:
                print ("********** 系统配置文件检查成功 **********")
                return 1
        except AttributeError as e:
            print ("********** 查询查询/etc/shadow子进程超时 **********")
            retry_times = retry_times + 1
            time.sleep(10)
            continue

def request_etc_file_content_3(conn):

    result = conn.exec_command('cat /etc/group|grep "root"')
    time.sleep(15)	
    return result	

def check_etc_file_content_3(conn):
	
    allow_retry_times = 120
    retry_times = 0
    while retry_times < allow_retry_times:
        t = MyThread(func=request_etc_file_content_3,args=(conn,))
        t.setDaemon(True)
        t.start()
        t.join(20)
        print ("********** 结束查询/etc/group的进程 **********")
        try:
            a = t.get_result()
            print (a)
            if (a is None):
                print ("********** 系统配置文件检查错误 **********")
                return 0
            else:
                print ("********** 系统配置文件检查成功 **********")
                return 1
        except AttributeError as e:
            print ("********** 查询查询/etc/group子进程超时 **********")
            retry_times = retry_times + 1
            time.sleep(10)
            continue
			
#重定向upgrade日志的输出
def change_upgrade_log_stdout(conn):

    conn.exec_command("sed -ie 's#/var/log/upgrade.log#/dev/ttyS0'#g /usr/share/onecloud-upgrade/upgrade_log.conf")
    time.sleep(1)
    conn.exec_command('cat /usr/share/onecloud-upgrade/upgrade_log.conf')
	
#检查标志文件
def check_flag_file(conn):
    data = conn.exec_command('ls -la /test_flags')
    data = data.decode('utf8')
    if ("No such file or directory" in data):
        print ("********** 标志文件删除**********")
        return 1
    else:
        print ("********** 标志文件存在 **********")
        return 0
		
if __name__ == "__main__":

    check_times = input("请输入测试次数：")
    check_times = int(check_times)
    test_times = 1
    ip = input("请输入测试设备的IP地址：")
    username = input("请输入测试设备的用户名：")
    password = input ("请输入测试设备的密码：")
	
    while test_times <= check_times:
	
        conn = SSHConnection(ip,22,username,password)
        time.sleep (5)
        data = conn.exec_command('ubus call upgrade get_status')
        data = data.decode('utf8')
        str_1 = "upgrade_local_version"
        if (str_1 in data):
            print ("********** SSH连接建立成功 **********")
        else:
            print ("********** SSH连接建立失败，重新尝试建立连接 **********")
            allow_retry_times = 360
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
                print ("********** 无法成功建立SSH连接 **********")
                continue
		
        #修改启动分区
        if (change_flags(conn) == 1):
            t = threading.Thread(target=reboot,args=(conn,))
            t.setDaemon(True)
            t.start()
            t.join(200)
            time.sleep(100)
            print("********** 结束等待重启的进程 **********")
        else:
            print ("********** 无法回退系统版本至V1.0.427，重新尝试修改标志位 **********")
            continue
		
        #检查系统是否成功回退至V1.0.427版本
        allow_retry_times = 60
        retry_times = 0
        while retry_times < allow_retry_times:
            if (check_ssh_connect(ip,username,password) == 1):
                print ("********** 设备重启完成 *********")
                conn.close()
                break
            else:
                retry_times = retry_times + 1
                time.sleep(10)
        if(retry_times == allow_retry_times):
            print ("********** 系统重启后,SSH连接建立超时 **********" )
            conn.close()
            continue
        else:
            conn = SSHConnection(ip,22,username,password)
            time.sleep(5)
            if (check_system_ver(conn) == 1):
                if (check_upgrade_ver(conn) == 1):
                    if (check_mount_structure(conn) == 0):
                        if (check_key_catalogues_1(conn) == 1):
                            if (check_rootfs(conn) == 0):
                                if (check_etc_file_content_1(conn) == 1 and check_etc_file_content_2(conn) == 1 and check_etc_file_content_3(conn) == 1):
                                    if (check_profile_size(conn) == 1):
                                        if (check_flag_file(conn) == 0):
                                            print ("********** No.%d:系统版本成功回退至V1.0.427 **********" %test_times)
                                            print ("********** 使用过渡版本upgrade升级整包 **********")
                                            print ("********** 开始第%d次升级 **********" %test_times)
                                            change_upgrade_log_stdout(conn)
                                            #conn.exec_command ('cp -f /media/sda1/2.0.1/onecloud-system_V2.0.1_arm.ipk /media/sda1')
                                            #time.sleep(5)
                                            t = threading.Thread(target=upgrade_1,args=(conn,))
                                            t.setDaemon(True)
                                            t.start()
                                            t.join(100)
                                            time.sleep(500)
                                            print("********** 结束等待升级的进程 **********")
                                            allow_retry_times = 60
                                            retry_times = 0
                                            while retry_times < allow_retry_times:
                                                if (check_ssh_connect(ip,username,password) == 1):
                                                    print ("********** 设备重启完成 *********")
                                                    conn.close()
                                                    break
                                                else:
                                                    retry_times = retry_times + 1
                                                    time.sleep(10)
                                            if(retry_times == allow_retry_times):
                                                print ("********** upgrade过渡版本整包升级测试，第%d次测试失败。 **********" %test_times)
                                                print ("********** 系统重启后,SSH连接建立超时 **********" )
                                                test_times = test_times + 1
                                                continue
                                        else:
                                            print ("********** No.%d:系统版本回滚失败 **********" %test_times)
                                            print ("********** 标志文件检查错误 **********")
                                            conn.exec_command('rm -f /test_flags')
                                            with open('D:/upgrade_1.2.3/427_应该存在标志文件.txt', 'a') as f:
                                                f.write('第%d次测试失败\n' %test_times)
                                            conn.close()
                                            test_times = test_times + 1
                                            continue
                                    else:
                                        print ("********** No.%d:系统版本回滚失败 **********" %test_times)
                                        print ("********** profile文件检查错误 **********")
                                        with open('D:/upgrade_1.2.3/427_profile文件大小异常.txt', 'a') as f:
                                            f.write('第%d次测试失败\n' %test_times)
                                        conn.close()
                                        test_times = test_times + 1
                                        continue
                                else:
                                    print ("********** No.%d:系统版本回滚失败 **********" %test_times)
                                    print ("********** /etc目录下文件检查错误 **********")
                                    with open('D:/upgrade_1.2.3/427_系统配置文件不正确.txt', 'a') as f:
                                        f.write('第%d次测试失败\n' %test_times)
                                    conn.close()
                                    test_times = test_times + 1
                                    continue
                            else:
                                print ("********** No.%d:系统版本回滚失败 **********" %test_times)
                                print ("********** 根文件系统类型检查错误 **********")
                                with open('D:/upgrade_1.2.3/427_根文件系统类型为overlay.txt', 'a') as f:
                                    f.write('第%d次测试失败\n' %test_times)
                                conn.close()
                                test_times = test_times + 1
                                continue
                        else:
                            print ("********** No.%d:系统版本回滚失败 **********" %test_times)
                            print ("********** 系统关键目录检查错误 **********")
                            with open('D:/upgrade_1.2.3/427_instaboot_otc_base目录存在.txt', 'a') as f:
                                f.write('第%d次测试失败\n' %test_times)
                            retry_times = retry_times + 1
                            conn.close()
                            test_times = test_times + 1
                            continue
                    else:
                        print ("********** No.%d:系统版本回滚失败 **********" %test_times)
                        print ("********** system包挂载结构检查错误 **********")
                        with open('D:/upgrade_1.2.3/427_instaboot分区挂载.txt', 'a') as f:
                            f.write('第%d次测试失败\n' %test_times)
                        conn.close()
                        test_times = test_times + 1
                        continue
                else:
                    print ("********** No.%d:系统版本回滚失败 **********" %test_times)
                    print ("********** upgrade版本检查错误，不为ver_1.2.3 **********")
                    with open('D:/upgrade_1.2.3/427_upgrade版本错误.txt', 'a') as f:
                        f.write('第%d次测试失败\n' %test_times)
                    conn.close()
                    test_times = test_times + 1
                    continue
            else:
                print ("********** No.%d:系统版本回滚失败 **********" %test_times)
                print ("********** 系统版本检查错误，不为ver_1.0.427 **********")
                with open('D:/upgrade_1.2.3/427_系统版本错误.txt', 'a') as f:
                    f.write('第%d次测试失败\n' %test_times)
                test_times = test_times + 1
                conn.close()
                continue
			

		#检查升级成功与否
        conn = SSHConnection(ip,22,username,password)
        time.sleep(5)
        if (check_system_ver(conn) == 0):
            if (check_upgrade_ver(conn) == 0):
                if (check_mount_structure(conn) == 1):
                    if (check_key_catalogues(conn) == 1):
                        if (check_rootfs(conn) == 1):
                            if (check_etc_file_content_1(conn) == 1 and check_etc_file_content_2(conn) == 1 and check_etc_file_content_3(conn) == 1):
                                if (check_profile_size(conn) == 1):
                                    if (check_flag_file(conn) == 1):
                                        print ("********** No.%d:过渡版本upgrade升级整包测试成功 **********" %test_times)
                                        with open('D:/upgrade_1.2.3/过渡版本upgrade升级整包测试成功.txt', 'a') as f:
                                            f.write('第%d次测试成功\n' %test_times)
                                        conn.exec_command('touch /test_flags')
                                        test_times = test_times + 1
                                        time.sleep(2)
                                        conn.close()
                                        continue
                                    else:
                                        print ("********** No.%d:过渡版本upgrade升级整包测试失败 **********" %test_times)
                                        print ("********** 标志文件检查错误 **********")
                                        with open('D:/upgrade_1.2.3/标志文件不应该存在.txt', 'a') as f:
                                            f.write('第%d次测试失败\n' %test_times)
                                        conn.close()
                                        test_times = tset_times + 1
                                        continue											
                                else:
                                    print ("********** No.%d:过渡版本upgrade升级整包测试失败 **********" %test_times)
                                    print ("********** profile文件检查错误 **********")
                                    with open('D:/upgrade_1.2.3/profile文件大小异常.txt', 'a') as f:
                                        f.write('第%d次测试失败\n' %test_times)
                                    conn.close()
                                    test_times = test_times + 1
                                    continue
                            else:
                                print ("********** No.%d:过渡版本upgrade升级整包测试失败 **********" %test_times)
                                print ("********** /etc目录下文件检查错误 **********")
                                with open('D:/upgrade_1.2.3/系统配置文件不正确.txt', 'a') as f:
                                    f.write('第%d次测试失败\n' %test_times)
                                conn.close()
                                test_times = test_times + 1
                                continue								
                        else:
                            print ("********** No.%d:过渡版本upgrade升级整包测试失败 **********" %test_times)
                            print ("********** 根文件系统类型不为overlay **********")
                            with open('D:/upgrade_1.2.3/根文件系统类型不为overlay.txt', 'a') as f:
                                f.write('第%d次测试失败\n' %test_times)
                            conn.close()
                            test_times = test_times + 1
                            continue
                    else:
                        print ("********** No.%d:过渡版本upgrade升级整包测试失败 **********" %test_times)
                        print ("********** /instaboot/otc_base不存在 **********")
                        with open('D:/upgrade_1.2.3/instaboot_otc_base目录不存在.txt', 'a') as f:
                            f.write('第%d次测试失败\n' %test_times)
                        conn.close()
                        test_times = test_times + 1
                        continue
                else:
                    print ("********** No.%d:过渡版本upgrade升级整包测试失败 **********" %test_times)
                    print ("********** /instaboot分区没有挂载 **********")
                    with open('D:/upgrade_1.2.3/instaboot分区没有挂载.txt', 'a') as f:
                        f.write('第%d次测试失败\n' %test_times)
                    conn.close()
                    test_times = test_times + 1
                    continue
            else:
                print ("********** No.%d:过渡版本upgrade升级整包测试失败 **********" %test_times)
                print ("********** upgrade版本检查错误 **********")
                with open('D:/upgrade_1.2.3/upgrade版本错误.txt', 'a') as f:
                    f.write('第%d次测试失败\n' %test_times)
                conn.close()
                test_times = test_times + 1
                continue
        else:
            print ("********** No.%d:过渡版本upgrade升级整包测试成功 **********" %test_times)
            print ("********** 系统版本检查错误 **********")
            with open('D:/upgrade_1.2.3/系统版本错误.txt', 'a') as f:
                f.write('第%d次测试失败\n' %test_times)
            conn.close()
            test_times = test_times + 1
            continue
		
    print ("********** upgrade过渡版本整包升级测试完成。**********")
    #msg = build_text_msg("过渡版本upgrade：整包在线升级长跑测试完成")
    #send_result = send_msg(msg)
    #r = json.loads(send_result)
    #if r["errcode"] == 0:
    #    print ("send msg Succ")
    #else:
    #    print ("send msg Failed")