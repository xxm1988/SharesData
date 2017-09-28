#! /bin/env python
#encoding=utf8
import sys,os
import pdb
import time
import urllib2
import sqlite3
import datetime
import platform
import tushare as ts
from ShareData import *
from sqlalchemy import create_engine
from multiprocessing.dummy import Pool as ThreadPool

class StockCommonData():
    def __init__(self):
        if platform.system() == "Windows":
            self.sqlitedb_engine = create_engine(u"sqlite:///F:\\百度云同步盘\\StockData\\stock_list.db")
            self.sqlitedb_conn   = sqlite3.connect(u"F:\\百度云同步盘\\StockData\\stock_list.db")
        else:
            self.sqlitedb_engine = create_engine(u"sqlite:////data/StockData/stock_list.db")
            self.sqlitedb_conn   = sqlite3.connect(u"/data/StockData/stock_list.db")

    def __del__(self):
        self.sqlitedb_conn.close()

    def exeSql(self,sql_cmd):
        cu = self.sqlitedb_conn.cursor()
        cu.execute(sql_cmd)
        return cu.fetchall()

    def exeSqlMany(self,sql_cmd,insertDataList):
        cu = self.sqlitedb_conn.cursor()
        cu.executemany(sql_cmd,insertDataList)
        return cu.fetchall()

    def CreateStockList(self):
        gsbObj = ts.get_stock_basics()
        gsbObj.to_sql('stock_list',self.sqlitedb_engine,if_exists='replace')

    def UpdateStockTerminnatedList(self):
        gsbObj = ts.get_terminated()
        gsbObj.to_sql('stock_terminated',self.sqlitedb_engine,if_exists='replace')

    def CreateStockList2(self):
        proxy_info = { 'host' : '10.134.5.88',
                       'port' : 8080
                     }
        # We create a handler for the proxy
        proxy_support = urllib2.ProxyHandler({"http" : "http://%(host)s:%(port)d" % proxy_info})
        # We create an opener which uses this handler:
        opener = urllib2.build_opener(proxy_support)
        # Then we install this opener as the default opener for urllib2:
        urllib2.install_opener(opener)
        print "hear"
        url = "http://ctxalgo.com/api/stocks"
        res = urllib2.urlopen(url)
        get_data = res.read()
        stock_dict = eval(get_data)
        import pdb
        pdb.set_trace()

        sql_cmd = """ DROP TABLE IF EXISTS stock_list_new ; """
        self.exeSql(sql_cmd)
        sql_cmd = """ CREATE TABLE IF NOT EXISTS [stock_list_new] (
                      [code] CHAR(10),
                      [name] CHAR(50)); """
        self.exeSql(sql_cmd)
        sql_cmd = """ insert into stock_list_new(code,name) values(?,?) """

        insertItemList = []
        for stock_code,stock_name in stock_dict.items():
            stock_code = stock_code[2:]
            insertItemList.append((stock_code,stock_name.decode('unicode_escape')  ))

        result = self.exeSqlMany(sql_cmd,insertItemList)
        self.sqlitedb_conn.commit()
        return result

    def GetStockList(self):
        sql_cmd = """ select code from stock_basics order by code"""
        return self.exeSql(sql_cmd)

    def GetStockList2(self):
        sql_cmd = """ select * from stock_list_new order by code"""
        return self.exeSql(sql_cmd)

    def GetStockIPOdate(self,stock_code):
        sql_cmd = """ select timeToMarket from stock_basics where code='%s' """ % stock_code
        cu = self.sqlitedb_conn.cursor()
        result = cu.execute(sql_cmd)
        for line in result:
            return line[0]
        return '19901210'

    def GetStockterminatedDict(self):
        sql_cmd = """ select code,tDate from stock_terminated """
        result = self.exeSql(sql_cmd)
        tmDict = {}
        for line in result:
            tmDict[line[0]] = line[1]
        return tmDict

    def GetStockDealDateList(self,stock_code):
        sql_cmd = """ select calendarDate from trade_calendar where isOpen=1 """
        result = self.exeSql(sql_cmd)
        dealDateList = []
        ipoDate    = self.GetStockIPOdate(stock_code)
        termDict   = self.GetStockterminatedDict()
        for line in result:
            if line[0] > ipoDate:
                if stock_code not in termDict.keys() or line[0] < termDict[stock_code]:
                    dealDateList.append(line[0])

        return dealDateList

def GetAlreadyGotCodeList():
    sqlitedb_conn  = sqlite3.connect(u"/data/StockData/stock_data_daily.db" )
    sql_cmd = """ select distinct code from stock_daily_data  """ 
    cu = sqlitedb_conn.cursor()
    result = cu.execute(sql_cmd)
    stock_list = []
    for line in result:
        stock_list.append(line[0])
    return stock_list

def CreateStockHistoryDailyDataMultiProcess(stock_code):
    if platform.system() == "Windows":
        sqlitedb_stock  = sqlite3.connect(u"sqlite:///F:\\百度云同步盘\\StockData\\%s\\stock_data_daily.db" )
    else:
        sqlitedb_stock  = sqlite3.connect(u"/data/StockData/stock_data_daily.db" )
    scObj  = ShareClass()
    try:
    	print "Begin to get [%s] " % stock_code
    	result = scObj.GetDayData(code=stock_code,end='2017-09-20',zs=False)
    	print "Finished get [%s]" % stock_code
    except Exception,e:
        print "Failed to get %s " % stock_code
    	print e
        return False
    try:
        print "Beging to save [%s]" % stock_code
        result.to_sql('stock_daily_data',sqlitedb_stock,if_exists='append')
        print "Finished save [%s]" % stock_code
        return True
    except Exception,e:
        print "Failed to save %s " % stock_code
	print e
        return False

if __name__ == "__main__":
    scdObj = StockCommonData()

    #os.environ['http_proxy']  = 'http://dev-proxy.oa.com:8080'
    #os.environ['https_proxy'] = 'http://dev-proxy.oa.com:8080'

    PROC_NUM = 1
    pool  = ThreadPool(PROC_NUM)
    count = 0

    #CreateStockHistoryDailyDataMultiProcess('000001')
    #sys.exit()
    #pdb.set_trace()

    stock_list   = scdObj.GetStockList()
    already_list = GetAlreadyGotCodeList()
    print "already get stock num is [%s]"  % len(already_list)
    for line in stock_list:
        stock_code = line[0]
	if str(stock_code) in already_list:
	    #print "[%s] Already got data,not need get yet!" % stock_code
	    continue
        count += 1
        if count%PROC_NUM == 0:
            pool.map(CreateStockHistoryDailyDataMultiProcess,((stock_code,)))
            paraList = []
            count = 0
