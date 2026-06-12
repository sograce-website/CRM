SOGRACE CRM Auto Collect V1.1 Pro

文件：
auto_collect_new.py

上传 GitHub 覆盖旧的 auto_collect_new.py。

服务器执行：
cd ~/crm
git fetch origin
git reset --hard origin/main
python3 -m py_compile auto_collect_new.py
> auto_collect_new.log
> auto_collect_debug_urls.txt
python3 auto_collect_new.py

看日志：
tail -n 100 auto_collect_new.log

看抓到的 Bing URL：
cat auto_collect_debug_urls.txt

网页启动：
https://crm.sograce.cn/auto_collect_new
