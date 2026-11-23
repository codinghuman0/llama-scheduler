// Exact declarations from both frozen sampler sources; read-only RNG inspection.
struct llama_sampler_backend {
    llama_sampler_backend(const char * name) : name(name), name_ext(name), is_init(false), support(false) {}

    const char * get_name() {
        if (!is_init) {
            return name.c_str();
        }

        if (support) {
            name_ext = "+" + name;
        } else {
            name_ext = "-" + name;
        }

        return name_ext.c_str();
    }

    void init(bool support) {
        GGML_ASSERT(this->is_init == false);

        this->is_init = true;
        this->support = support;
    }

private:
    std::string name;
    std::string name_ext;

    bool is_init;
    bool support;
};

struct llama_sampler_dist : public llama_sampler_backend {
    const uint32_t seed;
          uint32_t seed_cur;

    std::mt19937 rng;

    ggml_tensor * inp_uniform;
};
