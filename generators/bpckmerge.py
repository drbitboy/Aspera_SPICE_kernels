import os
import sys
import numpy as np
import spiceypy as sp

### Get script's name for internal filename and segment identifiers
try: my_name
except:
  my_name = os.path.basename(__file__).upper()
  if my_name.endswith('.PY'): my_name = my_name[:-3]
  if my_name[:-1].endswith('.PY'): my_name = my_name[:-4]
  def update_id(sid,L=40): return (f'{my_name}:{sid}')[:L]


########################################################################
class BPCKSEGMENT_TYPE02:
  """Model a Type 02 segment from next array of a binary PCK DAF"""
  def __init__(self, source):
    """source is a BPCK instance, called from its __init__ method"""
    ### Get and unpack segment'summary data
    (self.firstet,self.lastet
    ,),(self.clssid,self.baseid,self.pcktype,self.initialaddr
    ,self.finaladdr
    ,) = self.usumm = sp.dafus(sp.dafgs(), source.nd, source.ni)
    assert self.pcktype==2

    ### Get segment id
    ### Convert base frame ID to frame name
    self.name = sp.dafgn()
    self.frame = sp.frmnam(self.baseid,99)

    ### Read segment array
    segdata = sp.dafrda(source.handle,self.initialaddr,self.finaladdr)

    ### Last 2 elements are record size and record count
    ### Previous element is inteval length
    ### Previous elements to that is segment start time, and not used
    self.rsize,self.n = np.int32(segdata[-2:])
    self.intlen = segdata[-3]

    ### Calculate polynomial degree
    self.polydg = ((self.rsize - 2) // 3) - 1

    ### Reshape all preceding data into records, as 2D array
    self.recs = segdata[:-4].reshape((self.n,-1,))


  def etfilter(self, etstart, etstop, handle, pckopn_args):
    """
Identify this segments records that overlap a start/stop range filter.
If found, then write them into a new PCK, opening that PCK if needed

- etstart,etstop - range of ET filter
- handle - handle of opened binary PCK, or None if PCK not yet opened
- pckopn_args - argument list for sp.pckopn() call to create PCK

Returns
- output PCK handle
  - Handle value from caller is initially None
  - Handle value of None changed to integer on first overlapping segment
  - handle will be unchanged if there is no overlap
- Segment comments
  - list of strings if any records were written
  - None if no records were written

"""

    ### Skip this segment if its ET range is outside the ET filter
    if self.firstet > etstop: return handle, None
    if self.lastet < etstart: return handle, None

    ### Calculate (Midpoint+/-radius) for each record
    ### - stops and starts will be 1-D arrays
    stops = self.recs[:,0] + self.recs[:,1]
    starts = self.recs[:,0] - self.recs[:,1]

    ### Find records that overlap ET filter
    ### - return unchanged handle if not found (should not happen)
    iw = np.where(np.logical_and(stops >= etstart, starts <= etstop))
    n = len(iw[0])
    if not n: return handle, None

    ### Ensure those records are contiguous
    iwarr = iw[0]
    ihi,ilo = iwarr[[0,-1]]
    assert 1 == len(iwarr) or (iwarr[1:]-iwarr[:-1]).max() == 1

    ### Open new binary PCK, if not already open
    if None is handle: handle = sp.pckopn(*pckopn_args)

    ### Select filtered records
    filts = self.recs[iw]

    ### Calculate remaining arguments for pckw02 call
    first, last = filts[0,0] - filts[0,1], filts[-1,0] + filts[-1,1]
    segid = update_id(self.name)
    cdata = filts.flatten()

    sp.pckw02(handle, self.clssid, self.frame, first, last, segid
             , self.intlen, n, self.polydg, cdata, first
             )

    segcmts = [ f'  - from record offsets {ilo} to {ihi}, inclusive' ]

    ### return possibly updated handle, plus comments
    return handle, segcmts


########################################################################
class BPCK:
  """Model a Type 02 binary PCK"""
  def __init__(self,bpckfn):
    ### Open filename as a DAF; read first record
    self.bpckfn = bpckfn
    self.handle = sp.dafopr(self.bpckfn)
    self.nd, self.ni, self.locifn = sp.dafrfr(self.handle,1024)[:3]

    ### Search segements, model at Type 02 binay PCK segments
    self.segments = list()
    sp.dafbfs(self.handle)
    while sp.daffna():
      self.segments.append(BPCKSEGMENT_TYPE02(self))

    ### Clean up
    sp.dafcls(self.handle)
    del self.handle

  def etfilter(self, etstart, etstop, handle, pckopn_args):
    """
Filter each segment against ET range specification

See BPCKSEGMENT_TYPE02.etfilter method for argument and return
"""
    filcmts = None
    offset = -1
    for seg in self.segments:
      offset += 1
      handle, segcmts = seg.etfilter(etstart, etstop, handle, pckopn_args)

      ### Append segment comments to file commnet
      if None is segcmts: continue
      if None is filcmts:
        filcmts = [ f'File {self.bpckfn}:'
                  , f'- Internal filname [{self.locifn.strip()}]'
                  ]
      filcmts.extend(
        [ f'- Data added, from segment [{seg.name}] at offset {offset},'
        ] + segcmts
      )

    return handle, filcmts


########################################################################
def main(argv):

  bpcfns,ks,utcs,ets = list(),list(),list(),list()

  ### Each ommand-line argument is one of three items:
  for arg in argv:

    ### - Binary PCK filename, ending in .BPC or .bpc
    if arg.lower().endswith('.bpc'):
      bpcfns.append(arg)

    ### - Leapssecond kernel or meta-kernel ending in .tls or .tm
    elif arg.lower().endswith('.tls')or arg.lower().endswith('.tm'):
      ks.append(arg)

    ### - UTC range limit; high or low, only two will be used
    else:
      utcs.append(arg)

  ### First PCK filename is output PCK; ensure it does not exist; ...
  pckoutfn = bpcfns.pop(0)
  assert not os.path.exists(pckoutfn),f'Output PCK [{pckoutfn}] already exists'

  ### ... also ensure its directory does exist
  d = os.path.dirname(pckoutfn)
  assert os.path.exists(d and d or '.'),'Output PCK directory [{d}] does not exist'

  ### Load non-PCK-source kernels
  list(map(sp.furnsh, ks))

  ### Convert UTCs to ETs
  for utc in utcs:
    try   : ets.append(sp.utc2et(utc))
    except: print(f'- Ignoring argument [{utc}]')

  ### Find ED filter range limits
  etstart,etstop = ets = [min(ets),max(ets)]

  ### Initialize output PCK handle to None
  ### - Build argument list for sp.pckopn, so ET filter method can open
  handle = None
  pckopn_args = [pckoutfn, update_id(os.path.basename(pckoutfn),60),0]

  outcmts = list()

  ### Loop over PCK fileanmes, filter each one's data
  for bpcfn in bpcfns:
    handle,filcmts = BPCK(bpcfn).etfilter(etstart, etstop, handle, pckopn_args)
    if None is filcmts: continue
    outcmts.extend(filcmts)

  ### Check that data were written, write any comments, and clean up
  assert not (None is handle),'No data matched the ET range filter'

  if outcmts: sp.dafac(handle, outcmts)
  sp.dafcls(handle)


########################################################################
if "__main__" == __name__:
  main(sys.argv[1:])
