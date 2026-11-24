/* SPDX-License-Identifier: GPL-2.0 */
#ifndef UNIVERSAL_GUARD_DOMAIN_H
#define UNIVERSAL_GUARD_DOMAIN_H
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "new_a.h"
struct ug_domain {
    uint32_t magic,version,limit,count,owner,uid;
    uint64_t start_ticks;
    unsigned char possible[NEW_A_MAX_CPUS],online[NEW_A_MAX_CPUS],allowed[NEW_A_MAX_CPUS],selected[NEW_A_MAX_CPUS];
};
_Static_assert(sizeof(struct ug_domain)==4128,"Guard ABI");
_Static_assert(CPU_SETSIZE==NEW_A_MAX_CPUS,"Affinity bounds");
static struct ug_domain ug;
static int analysis_possible_ids[NEW_A_MAX_CPUS];
static int ug_parse(const char *text,unsigned char *mask)
{
    unsigned long previous=0;int found=0;memset(mask,0,NEW_A_MAX_CPUS);
    for(;;){char *end;errno=0;if(!isdigit((unsigned char)*text))return -1;unsigned long low=strtoul(text,&end,10),high=low;
        if(errno || low>=NEW_A_MAX_CPUS || (found && low<=previous))return -1;text=end;
        if(*text=='-'){text++;if(!isdigit((unsigned char)*text))return -1;high=strtoul(text,&end,10);if(errno || high<low || high>=NEW_A_MAX_CPUS)return -1;text=end;}
        for(unsigned long c=low;c<=high;c++)mask[c]=1;previous=high;found=1;
        if(*text!=',')break;text++;
    }
    while(isspace((unsigned char)*text))text++;return found && !*text?0:-1;
}
static int ug_read_mask(const char *path,unsigned char *mask)
{
    char text[NEW_A_MAX_CPUS*6];FILE *f=fopen(path,"re");if(!f)return -1;
    int ok=fgets(text,sizeof(text),f) && fgetc(f)==EOF && !ferror(f);fclose(f);return ok?ug_parse(text,mask):-1;
}
static unsigned long long ug_ticks(pid_t pid)
{
    char path[96],text[4096];snprintf(path,sizeof(path),"/proc/%d/stat",pid);FILE *f=fopen(path,"re");if(!f)return 0;
    int ok=fgets(text,sizeof(text),f)!=NULL;fclose(f);if(!ok)return 0;char *last=strrchr(text,')'),*save=NULL;if(!last)return 0;
    char *part=strtok_r(last+2," ",&save);for(int i=0;i<19 && part;i++)part=strtok_r(NULL," ",&save);return part?strtoull(part,NULL,10):0;
}
static int ug_affinity(pid_t pid,const unsigned char *wanted,int policy)
{
    cpu_set_t set;if(sched_getaffinity(pid,sizeof(set),&set))return -1;
    if(policy>=0 && sched_getscheduler(pid)!=policy)return -1;
    for(int c=0;c<NEW_A_MAX_CPUS;c++)if(CPU_ISSET(c,&set)!=(wanted[c]!=0))return -1;return 0;
}
static int ug_current(void)
{
    unsigned char mask[NEW_A_MAX_CPUS];char path[96],line[512];unsigned int a,b,c,d;int uid_ok=0;
    if(ug_read_mask("/sys/devices/system/cpu/possible",mask) || memcmp(mask,ug.possible,sizeof(mask)))return -1;
    if(ug_read_mask("/sys/devices/system/cpu/online",mask) || memcmp(mask,ug.online,sizeof(mask)))return -1;
    if(ug_ticks(ug.owner)!=ug.start_ticks || ug_affinity(ug.owner,ug.allowed,SCHED_OTHER))return -1;
    snprintf(path,sizeof(path),"/proc/%u/status",ug.owner);FILE *f=fopen(path,"re");if(!f)return -1;
    while(fgets(line,sizeof(line),f))if(sscanf(line,"Uid: %u %u %u %u",&a,&b,&c,&d)==4){uid_ok=a==ug.uid && b==ug.uid && c==ug.uid && d==ug.uid;break;}
    fclose(f);return uid_ok?0:-1;
}
static int ug_load(const char *path)
{
    int fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);struct stat st;if(fd<0)return -1;
    ssize_t n=read(fd,&ug,sizeof(ug));char extra;int end=read(fd,&extra,1);int bad=fstat(fd,&st);close(fd);
    if(bad || n!=sizeof(ug) || end!=0 || !S_ISREG(st.st_mode) || st.st_uid!=ug.uid || st.st_mode&0022 || ug.magic!=0x4e415547 || ug.version!=1 || !ug.uid || ug.owner<=1 || !ug.start_ticks || !ug.limit || ug.limit>NEW_A_MAX_CPUS)return -1;
    unsigned int count=0,last=0,chosen=0;
    for(int c=0;c<NEW_A_MAX_CPUS;c++){
        if(ug.possible[c]>1 || ug.online[c]>1 || ug.allowed[c]>1 || ug.selected[c]>1)return -1;
        if((ug.online[c] || ug.allowed[c]) && !ug.possible[c])return -1;
        if(ug.selected[c] && !(ug.online[c] && ug.allowed[c]))return -1;
        if(ug.possible[c]){analysis_possible_ids[count++]=c;last=c+1;}chosen+=ug.selected[c];
    }
    if(!chosen || count!=ug.count || last!=ug.limit)return -1;return ug_current();
}
#endif
