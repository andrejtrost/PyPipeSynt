def FM(a, b, f1, f2, gain, sel):
    add = a + b
    sub = a - b

    if sel:
        mod = (add*461 + ((sub*f2) >> 16)*461 + f1*102) >> 10
    else:
        mod = add 

    z = mod * gain >> 8
    
    return mod, z
    

