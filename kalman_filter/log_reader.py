def reader_logs(uwb_str):
    store_ranges = {}
    x_sat = ""
    range = 0
    temp_str = uwb_str.split(' ')
    if temp_str[0] == 'dwm>':
        pass
    elif temp_str[0] != '\n':
        for temp_char in temp_str:
            if temp_char.split('=')[0] == 'le_us':
                break
            if temp_char.split('[')[0] == '\r\n':
                break
            name_sat = temp_char.split('[')[0]
            try:
                x_sat = temp_char.split('[')[1].split(']')[0].split(',')
                range = float(temp_char.split('[')[1].split(']')[1].split('=')[1])
            except:
                pass

            store_ranges[name_sat] = {'x_sat': x_sat, 'range': range}
    elif temp_str[0] == '\n':
        pass
    return store_ranges


if __name__ == '__main__':
    store = reader_logs(str("1A94[0.00,3.00,1.20]=1.78 C58A[3.00,3.00,1.20]=1.79 08DA[0.00,0.00,1.20]=2.76 1499[3.00,0.00,1.20]=3.02"))

    print(store)
