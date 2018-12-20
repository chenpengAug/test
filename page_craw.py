import os
import re
import sys
from multiprocessing import Process
from urllib.request import urlretrieve
import requests
from bs4 import BeautifulSoup


'''
需要修改项：global_path
global_path: 值为静态资源的家目录
入口页面： ${global_path}/home.html
注意：不可去掉末尾的 '/'
'''
global_path = "~/wx_craw/"


# 获取所有的静态资源文件,
# soup, 主页面html对象
# char_count, "/"的个数，用来拼接相对路径
# eg: count("/") = 2, path = ../../
def get_static_resource_to_local(soup, char_count):
    positive_path_prefix = ""
    for i in range(char_count):
        positive_path_prefix += "../"
    # 过滤掉不含 “href”, "src" 属性的资源文件
    css = soup.find_all('link', href=re.compile('.*'))
    # 藏在css的url中的图片
    css_inner = soup.find_all("style")
    js = soup.find_all('script', src=re.compile('.*'))
    img = soup.find_all("img", src=re.compile(".*"))
    video = soup.find_all("video", src=re.compile('.*'))
    get_inner_url(css_inner, positive_path_prefix)
    get_text(css, "href", positive_path_prefix)
    get_text(js, "src", positive_path_prefix)
    get_byte(img, "src", positive_path_prefix)
    get_byte(video, "src", positive_path_prefix)


def get_inner_url(tags, positive_path_prefix):
    for tg in tags:
        replace_url = re.sub("url\([\'\"]*//", "url(https://", tg.string)
        tg.string.replace_with(replace_url)
        its = re.finditer("url\([^\'\"\)]*", tg.string)
        for it in its:
            net_url = it.group().replace("url(", "")
            absolute_path = re.sub("^(https:)*//[^/]*/", "", net_url)
            # 替换掉其他奇怪的字符资源
            absolute_path = re.sub("[^\w\./]", "_", absolute_path)
            local_path = global_path + absolute_path
            net_to_local(net_url, local_path)
            print("it: {},  val: {} ".format(it, net_url))
        replace_url = re.sub("(https:)*//[^/]*/", positive_path_prefix, tg.string)
        tg.string.replace_with(replace_url)


# get_byte 和 get_text 公共处理方法
def common_get_resource(tg, attr, positive_path_prefix):
    # 先替换成网络的绝对资源位置
    net_url = re.sub("^(https:)*//", "https://", tg[attr])
    local_path = ""
    # 如果容错处理
    if "https://" not in net_url:
        return net_url, local_path
    # 再替换成本地的绝对资源位置
    # absolute_path = re.sub("(https://res\.wx\.qq\.com/)|(https://weixin\.qq\.com/)", "", net_url)
    absolute_path = re.sub("^(https:)*//[^/]*/", "", net_url)
    # 替换掉其他奇怪的字符资源
    absolute_path = re.sub("[^\w\./]", "_", absolute_path)
    # 资源文件的引用地址
    tg[attr] = positive_path_prefix + absolute_path
    # 资源文件本地存放地址
    local_path = global_path + absolute_path
    return net_url, local_path


# img是二进制文件，需要另外设置方法读写
def get_byte(tags, attr, positive_path_prefix=""):
    for tg in tags:
        net_url, local_path = common_get_resource(tg, attr, positive_path_prefix)
        dir_name = os.path.dirname(local_path)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        urlretrieve(net_url, filename=local_path)


# 网络资源下载到本地
def net_to_local(net_url, local_path):
    dir_name = os.path.dirname(local_path)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    urlretrieve(net_url, filename=local_path)


# 获取文本形式的资源文件
def get_text(tags, attr, positive_path_prefix=""):
    for tg in tags:
        net_url, local_path = common_get_resource(tg, attr, positive_path_prefix)
        # 如果容错处理
        if "https://" not in net_url:
            continue
        # 根据网络的资源位置去找资源
        sp = get_soup_with_url(net_url)
        write_to_local(local_path, sp.prettify())


# 获取soup对象
def get_soup_with_url(url):
    header = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, sdch',
        'Accept-Language': 'zh-CN,zh;q=0.8',
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.235'
    }

    req = requests.get(url, headers=header)
    req.encoding = 'utf-8'
    soup = BeautifulSoup(req.text, "html.parser")  # 创建BeautifulSoup对象
    return soup


# 获取主页面所有的a标签
def get_all_a_tag(soup):
    a_tags = soup.find_all('a', href=re.compile("/cgi-bin/readtemplate*"))
    return a_tags


# 页面设置到磁盘
def write_to_local(file_name, html_str):
    # html_str = html_str.replace("//res.wx.qq.com/", global_path)
    # html_str = html_str.replace("//weixin.qq.com/", global_path)
    html_str = re.sub("^(https:)*//[^/]*/", global_path, html_str)
    dir_name = os.path.dirname(file_name)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    if os.path.isdir(file_name):
        return
    with open(file=file_name, mode="w", encoding='utf-8') as f:
        f.write(html_str)


# 原始路径包含的特殊字符全部替换成“_”
def get_a_tag_local_path(a_tag):
    href = a_tag["href"]
    a_origin_path = href.split("t=")[1]
    a_local_file = re.sub("\W", "_", a_origin_path) + ".html"
    a_absolute_path = global_path + a_local_file
    return a_absolute_path, a_local_file


# 获取各个a标签的内容，以及资源文件
def get_a_tag(a_tags):
    index = 0
    for a_tag in a_tags:
        # 获取a的本地绝对路径和相对路径
        absolute_path, positive_path = get_a_tag_local_path(a_tag)
        # 获取a的真实网络资源位置
        a_url = a_tag["href"].replace("/cgi-bin/readtemplate", "https://weixin.qq.com/cgi-bin/readtemplate")
        try:
            # 获取a的内容
            a_tag_soup = get_soup_with_url(a_url)
            # 设置home.html中a的位置
            a_tag["href"] = positive_path
            # 获取a标签的资源文件
            get_static_resource_to_local(a_tag_soup, positive_path.count("/"))
            write_to_local(absolute_path, a_tag_soup.prettify())
        except Exception as e:
            print(e)
        index += 1
        print("net_url: {} , local_path: {} , count: {}".format(a_url, global_path + positive_path, index))


def get_home(url):
    home_soup = get_soup_with_url(url)
    get_static_resource_to_local(home_soup, 0)
    # 获取各个a标签的内容
    # a_tags = get_all_a_tag(home_soup)

    # print('Parent process %s.' % os.getpid())
    # p = Process(target=get_a_tag, args=(a_tags, ))
    # print('Child process will start.')
    # p.start()
    # p.join()
    # print('Child process end.')

    # 获取各级子页面
    # get_a_tag(a_tags)
    # 写主页面的链接
    write_to_local(global_path + "home.html", home_soup.prettify())
    print("SUCCESS")


if __name__ == '__main__':

    url = "https://im.qq.com/"
    url = "https://www.alipay.com/"
    url = "https://www.jd.com"
    url = "https://cloud.tencent.com/product/mta"
    # url = "https://www.apple.com/cn/?afid=p238%7CtHpnaZWQ_mtid_18707vxu38484&cid=aos-cn-kwba-brand-bz"
    # url = "https://weixin.qq.com/cgi-bin/readtemplate?uin=&stype=&promote=&fr=&lang=zh_CN&ADTAG=&check=false&nav=faq&t=weixin_faq_list"

    # 没有输入本地资源存放路径
    if len(sys.argv) < 2:
        print("Default file path is: {} ,  You must set a local file path".format(global_path))
        exit(-1)
    else:
        # 参数中读取路径
        global_path = str(sys.argv[1])
        # 目录没有以/结尾，则手动加上/
        if not global_path.endswith("/"):
            global_path += "/"
        print("The file path is: {}".format(global_path))
    get_home(url)

