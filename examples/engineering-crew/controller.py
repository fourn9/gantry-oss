"""Discrete position-command filter; software model, not a motor simulation."""
def simulate(target, offset, initial=0.0, steps=80):
    position=initial; trace=[]
    for tick in range(steps):
        position += .25*(target+offset-position)
        trace.append({'tick':tick,'position_mm':position})
    return trace
