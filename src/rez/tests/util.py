
def _stdout(proc):
    out_,_ = proc.communicate()
    return out_.strip()
