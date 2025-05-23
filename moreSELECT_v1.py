import mysql.connector, dbfunc
conn = dbfunc.getConnection()   #connection to DB'             #DB Name
TABLE_NAME = 'bookings'

SELECT_statement = 'SELECT * FROM ' + TABLE_NAME +';'   
if conn != None:    #Checking if connection is None
    if conn.is_connected(): #Checking if connection is established
        print('MySQL Connection is established')                          
        dbcursor = conn.cursor()    #Creating cursor object database                
        dbcursor.execute(SELECT_statement)   
        print('SELECT statement executed successfully.') 
        row = dbcursor.fetchone()
        while row is not None:
            print(row[1], row[2], '\n')
            row = dbcursor.fetchone()                      
        dbcursor.close()              
        conn.close() #Connection must be closed
    else:
        print('DB connection error')
else:
    print('DBFunc error')
#Name:Ethan Williams
#Student Number: 24026055