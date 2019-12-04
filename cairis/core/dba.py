#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing,
#  software distributed under the License is distributed on an
#  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#  KIND, either express or implied.  See the License for the
#  specific language governing permissions and limitations
#  under the License.


import MySQLdb
from .ARM import *
from MySQLdb._exceptions import DatabaseError, IntegrityError
from .Borg import Borg
import os
from random import choice
import string

__author__ = 'Shamal Faily'

def canonicalDbUser(dbUser):
  return dbUser.replace('@','_at_').replace('.','_dot_')[:32]

def canonicalDbName(dbUser):
  return dbUser.replace('@','_at_').replace('.','_dot_')[:64]

def dbtoken(rPasswd,dbHost,dbPort,dbUser):
  try:
    rootConn = MySQLdb.connect(host=dbHost,port=int(dbPort),user='root',passwd=rPasswd)
    rootCursor = rootConn.cursor()
    sqlTxt = 'select dbtoken from cairis_user.auth_user where email="' + dbUser + '"'
    rs = rootCursor.execute(sqlTxt)
    if (rs != 1):
      exceptionText = 'MySQL error getting token for ' + dbUser 
      raise DatabaseProxyException(exceptionText) 
    else:
      t = rootCursor.fetchone()
    rootCursor.close()
    rootConn.close()
    return t[0]
  except DatabaseError as e:
    exceptionText = 'MySQL error getting token for ' + dbUser + ': ' + format(e)
    raise DatabaseProxyException(exceptionText) 

def createDatabaseSchema(rootDir,dbHost,dbPort,dbUser,dbPasswd,dbName):
  srcDir = rootDir + '/sql'
  initSql = srcDir + '/init.sql'
  procsSql = srcDir + '/procs.sql'
  dbUser = canonicalDbUser(dbUser)
  dbName = canonicalDbName(dbName)
  cmd = '/usr/bin/mysql -h ' + dbHost + ' --port=' + str(dbPort) + ' --user ' + dbUser + ' --password=\'' + dbPasswd + '\'' + ' --database ' + dbName + ' < ' + initSql
  os.system(cmd)
  cmd = '/usr/bin/mysql -h ' + dbHost + ' --port=' + str(dbPort) + ' --user ' + dbUser + ' --password=\'' + dbPasswd + '\'' + ' --database ' + dbName + ' < ' + procsSql
  os.system(cmd)

def createDefaults(rootDir,dbHost,dbPort,dbUser,dbPasswd,dbName):
  dbUser = canonicalDbUser(dbUser)
  dbName = canonicalDbName(dbName)
  srcDir = rootDir + '/sql'
  defaultSql = srcDir + '/default.sql'
  cmd = '/usr/bin/mysql -h ' + dbHost + ' --port=' + str(dbPort) + ' --user ' + dbUser + ' --password=\'' + dbPasswd + '\'' + ' --database ' + dbName + ' < ' + defaultSql
  os.system(cmd)


def runAdminCommands(adminPasswd,dbHost,dbPort,stmts,adminUser='root'):
  try:
    rootConn = MySQLdb.connect(host=dbHost,port=int(dbPort),user=adminUser,passwd=adminPasswd)
    rootCursor = rootConn.cursor()
    for stmt in stmts:
      rootCursor.execute(stmt)
    rootCursor.close()
    rootConn.close()
  except DatabaseError as e:
    exceptionText = 'MySQL error running "' + ', '.join(stmts) + '": message:' + format(e) 
    raise DatabaseProxyException(exceptionText) 

def createDatabaseAccount(rPasswd,dbHost,dbPort,dbUser,dbPasswd):
  stmts = ['drop user if exists ' + dbUser,
           "create user if not exists '" + dbUser + "'@'" + "%' identified by '" + dbPasswd + "'",
           'flush privileges']
  runAdminCommands(rPasswd,dbHost,dbPort,stmts)

def createDbOwnerDatabase(rPasswd,dbHost,dbPort):
  stmts = ['drop database if exists `cairis_owner`',
           'create database cairis_owner',
           'create table cairis_owner.db_owner(db varchar(64), owner varchar(32), primary key(db,owner)) engine=innodb']
  runAdminCommands(rPasswd,dbHost,dbPort,stmts)

def createDatabaseAndPrivileges(rPasswd,dbHost,dbPort,dbUser,dbPasswd,dbName):
  dbUser = canonicalDbUser(dbUser)
  dbName = canonicalDbName(dbName)
  stmts = ['drop database if exists `' + dbName + '`',
           'delete from cairis_owner.db_owner where db = "' + dbName + '"',
           'create database ' + dbName,
           "grant all privileges on `" + dbName + "`.* TO '" + dbUser + "'@'%'",
           'alter database ' + dbName + ' default character set utf8mb4',
           'alter database ' + dbName + ' default collate utf8mb4_general_ci',
           'flush tables',
           'flush privileges',
           'insert into cairis_owner.db_owner(db,owner) values("' + dbName + '","' + dbUser + '")',
           'commit']
  runAdminCommands(rPasswd,dbHost,dbPort,stmts)

def dropCairisUserDatabase(rPasswd,dbHost,dbPort):
  stmts = ['drop database if exists cairis_user']
  runAdminCommands(rPasswd,dbHost,dbPort,stmts)

def createCairisUserDatabase(rPasswd,dbHost,dbPort):
  stmts = ['create database if not exists cairis_user',
           'set global max_sp_recursion_depth = 255',
           'flush privileges']
  runAdminCommands(rPasswd,dbHost,dbPort,stmts)

def grantDatabaseAccess(rPasswd,dbHost,dbPort,dbName,dbUser):
  owner = dbOwner(dbName)
  stmts = ["grant all privileges on " + owner + "_" + dbName + ".* to '" + canonicalDbUser(dbUser) + "'@'%'"]
  runAdminCommands(rPasswd,dbHost,dbPort,stmts)

def revokeDatabaseAccess(rPasswd,dbHost,dbPort,dbName,dbUser):
  owner = dbOwner(dbName)
  stmts = ["revoke all privileges on " + owner + "_" + dbName + ".* from '" + canonicalDbUser(dbUser) + "'@'%'"]
  runAdminCommands(rPasswd,dbHost,dbPort,stmts)

def rootResponseList(sqlTxt):
  b = Borg()
  try:
    rootConn = MySQLdb.connect(host=b.dbHost,port=int(b.dbPort),user='root',passwd=b.rPasswd)
    rootCursor = rootConn.cursor()
    rs = rootCursor.execute(sqlTxt)
    responseList = []
    if (rs > 0):
      for row in rootCursor.fetchall():
        if (len(row) > 1):
          responseList.append(tuple(list(row)))
        else:
          responseList.append(list(row)[0])
    rootCursor.close()
    rootConn.close()
    return responseList
  except DatabaseError as e:
    exceptionText = 'MySQL error getting responses: ' + format(e)
    raise DatabaseProxyException(exceptionText) 

def dbOwner(dbName):
  sqlTxt = 'select owner from cairis_owner.db_owner where db like "%' + dbName + '"'
  rows = rootResponseList(sqlTxt)
  if (len(rows) == 0):
    raise DatabaseProxyException(dbName + ' or its owner not found') 
  else:
    return rows[0]

def isOwner(dbUser, dbName):
  db_owner = dbOwner(dbName)
  if (dbUser == db_owner):
    return True
  else:
    return False

def databases(dbUser):
  sqlTxt = 'select m.Db, co.owner from mysql.db m, cairis_owner.db_owner co where m.User = "' + dbUser + '" and m.Db = co.db'
  return rootResponseList(sqlTxt)

def existingAccount(userId):
  sqlTxt = "select count(email) from cairis_user.auth_user where email = '" + userId + "'"
  return rootResponseList(sqlTxt)[0]

def dbExists(dbName):
  sqlTxt = "select count(db) from cairis_owner.db_owner where db= '" + dbName + "'"
  return rootResponseList(sqlTxt)[0]

def dbUsers(dbName):
  sqlTxt = "select au.email from mysql.db db, cairis_user.auth_user au where db.Db = '" + dbName + "' and db.User = au.account and db.User not in (select owner from cairis_owner.db_owner where db ='" + dbName + "')"
  rows = rootResponseList(sqlTxt)
  if (len(rows) == 0):
    return []
  else:
    return rows

def accounts(rPasswd,dbHost,dbPort):
  sqlTxt = 'select email from cairis_user.auth_user'
  return rootResponseList(sqlTxt)

def dropUser(rPasswd,dbHost,dbPort,email):
  dbUser = canonicalDbUser(email)
  stmts = []
  for dbName,dbOwner in databases(dbUser):
    stmts.append('drop database if exists ' + dbName)
    stmts.append('flush privileges')
    stmts.append('delete from cairis_owner.db_owner where db = "' + dbName + '"')
  stmts.append('drop user if exists ' + dbUser)
  stmts.append('flush privileges')
  stmts.append('delete from cairis_user.auth_user where email = "' + email + '"')
  stmts.append('commit')
  runAdminCommands(rPasswd,dbHost,dbPort,stmts)

def resetUser(cairisRoot,rPasswd,dbHost,dbPort,email):
  dbUser = canonicalDbUser(email)
  stmts = []
  for dbName,dbOwner in databases(dbUser):
    stmts.append('drop database if exists ' + dbName)
    stmts.append('flush privileges')
    stmts.append('delete from cairis_owner.db_owner where db = "' + dbName + '"')
    stmts.append('commit')
  runAdminCommands(rPasswd,dbHost,dbPort,stmts)
  rp = dbtoken(rPasswd,dbHost,dbPort,email)
  createDatabaseAndPrivileges(rPasswd,dbHost,dbPort,dbUser,rp,dbUser + '_default')
  createDatabaseSchema(cairisRoot,dbHost,dbPort,email,rp,dbUser + '_default')
  createDefaults(cairisRoot,dbHost,dbPort,email,rp,dbUser + '_default')

def resetUsers(cairisRoot,rPasswd,dbHost,dbPort):
  for email in accounts(rPasswd,dbHost,dbPort):
    resetUser(cairisRoot,rPasswd,dbHost,dbPort,email)
