/* SPDX-License-Identifier: GPL-2.0 */
#ifndef UNIVERSAL_IDENTITY_H
#define UNIVERSAL_IDENTITY_H
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <linux/if_alg.h>
#include <sys/socket.h>
#include <sys/stat.h>
static void *universal_object_bytes;
static struct bpf_object *universal_open(const char *path)
{
    int fd=-1,algorithm=-1,operation=-1;struct stat st;struct bpf_object *obj=NULL;
    unsigned char digest[32];char rendered[65];struct sockaddr_alg addr={.salg_family=AF_ALG,.salg_type="hash",.salg_name="sha256"};
    fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
    if(fd<0 || fstat(fd,&st) || !S_ISREG(st.st_mode) || st.st_size<=0 || st.st_size>8*1024*1024)goto out;
    universal_object_bytes=malloc((size_t)st.st_size);if(!universal_object_bytes)goto out;
    size_t offset=0;while(offset<(size_t)st.st_size){ssize_t n=read(fd,(char *)universal_object_bytes+offset,(size_t)st.st_size-offset);if(n<=0)goto out;offset+=(size_t)n;}
    char extra;if(read(fd,&extra,1)!=0)goto out;
    algorithm=socket(AF_ALG,SOCK_SEQPACKET|SOCK_CLOEXEC,0);if(algorithm<0 || bind(algorithm,(struct sockaddr *)&addr,sizeof(addr)))goto out;
    operation=accept4(algorithm,NULL,NULL,SOCK_CLOEXEC);if(operation<0)goto out;
    offset=0;while(offset<(size_t)st.st_size){size_t n=(size_t)st.st_size-offset;if(n>32768)n=32768;ssize_t done=send(operation,(char *)universal_object_bytes+offset,n,MSG_MORE);if(done<=0)goto out;offset+=(size_t)done;}
    if(send(operation,NULL,0,0)!=0 || read(operation,digest,sizeof(digest))!=sizeof(digest))goto out;
    for(int i=0;i<32;i++)snprintf(rendered+2*i,3,"%02x",digest[i]);
    if(strcmp(rendered,UNIVERSAL_OBJECT_SHA256))goto out;
    obj=bpf_object__open_mem(universal_object_bytes,(size_t)st.st_size,NULL);
out:
    if(fd>=0)close(fd);if(operation>=0)close(operation);if(algorithm>=0)close(algorithm);
    if(!obj){free(universal_object_bytes);universal_object_bytes=NULL;fprintf(stderr,"UNIVERSAL_OBJECT_INTEGRITY_FAILED\n");}return obj;
}
static int universal_attest(struct bpf_object *object)
{
    struct bpf_program *program;int count=0;
    fprintf(stderr,"UNIVERSAL_OBJECT_IDENTITY {\"object_sha256\":\"%s\",\"programs\":[",UNIVERSAL_OBJECT_SHA256);
    bpf_object__for_each_program(program,object){if (!bpf_program__autoload(program)) continue;struct bpf_prog_info info={};__u32 size=sizeof(info);
        if(bpf_obj_get_info_by_fd(bpf_program__fd(program),&info,&size) || !info.id || !info.btf_id)return -1;
        fprintf(stderr,"%s{\"symbol\":\"%s\",\"id\":%u,\"btf_id\":%u,\"type\":%u,\"tag\":\"",count?",":"",bpf_program__name(program),info.id,info.btf_id,info.type);
        for(int i=0;i<8;i++)fprintf(stderr,"%02x",info.tag[i]);fputs("\"}",stderr);count++;
    }
    fputs("]}\n",stderr);return count==10?0:-1;
}
#endif
