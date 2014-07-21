#
# Simplest hessian client example
#

if __name__ == '__main__':
    import client
    
    proxy = client.HessianProxy("http://www.caucho.com/hessian/test/basic")
    print proxy.hello()
